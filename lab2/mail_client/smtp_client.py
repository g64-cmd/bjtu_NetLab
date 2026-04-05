"""
SMTP客户端 - 基于socket手动实现SMTP协议（RFC 821）

支持的SMTP命令：HELO, AUTH LOGIN, MAIL FROM, RCPT TO, DATA, QUIT, RSET, VRFY, NOOP
"""

import socket
import ssl
import base64
import datetime
import os
import mimetypes


class SMTPError(Exception):
    """SMTP协议错误"""
    pass


class SMTPClient:
    """
    SMTP客户端 - 通过TCP连接与SMTP服务器通信，发送邮件

    用法:
        client = SMTPClient()
        client.connect_ssl("smtp.qq.com", 465)
        client.login("user@qq.com", "授权码")
        client.send_mail("user@qq.com", ["a@b.com"], "主题", "正文")
        client.quit()
    """

    def __init__(self, timeout=15, debug=True):
        self.timeout = timeout
        self.debug = debug
        self.socket = None
        self.reader = None
        self.writer = None

    # ========== 连接管理 ==========

    def connect(self, server, port=25):
        """建立明文TCP连接到SMTP服务器"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect((server, port))
        self._setup_streams(sock)
        greeting = self._read_response()
        self._check_response(greeting, "220")
        return greeting

    def connect_ssl(self, server, port=465):
        """通过SSL/TLS连接到SMTP服务器"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect((server, port))
        context = ssl.create_default_context()
        sock = context.wrap_socket(sock, server_hostname=server)
        self._setup_streams(sock)
        greeting = self._read_response()
        self._check_response(greeting, "220")
        return greeting

    def _setup_streams(self, sock):
        """初始化读写流"""
        self.socket = sock
        self.reader = sock.makefile('rb')
        self.writer = sock

    def disconnect(self):
        """断开连接"""
        try:
            if self.reader:
                self.reader.close()
            if self.socket:
                self.socket.close()
        except Exception:
            pass
        finally:
            self.socket = None
            self.reader = None
            self.writer = None

    # ========== 底层协议方法 ==========

    def _send_command(self, command, expected_code=None):
        """
        发送SMTP命令并读取一行响应

        Args:
            command: 要发送的命令字符串
            expected_code: 期望的响应码（如"250"），为None则不检查

        Returns:
            服务器响应字符串
        """
        if self.debug:
            print(f"    C: {command}")
        self.writer.sendall((command + "\r\n").encode('utf-8'))
        response = self._read_response()
        if expected_code:
            self._check_response(response, expected_code)
        return response

    def _read_response(self):
        """
        读取服务器响应（可能包含多行，以三位数字+空格开头的行作为结束行）
        """
        lines = []
        while True:
            line = self.reader.readline()
            if not line:
                break
            line = line.decode('utf-8', errors='replace').rstrip('\r\n')
            if self.debug:
                print(f"    S: {line}")
            lines.append(line)
            # 第4个字符是空格（不是"-"），说明这是最后一行
            if len(line) >= 4 and line[3] == ' ':
                break
            if len(line) == 3:
                break
        return '\n'.join(lines)

    def _check_response(self, response, expected_code):
        """检查响应码是否符合预期"""
        if not response:
            raise SMTPError("服务器未响应")
        code = response[:3]
        if code != expected_code:
            raise SMTPError(f"SMTP错误，期望 {expected_code}，收到: {response.strip()}")

    # ========== SMTP 命令 ==========

    def helo(self, hostname=None):
        """发送HELO命令，标识客户端主机"""
        if not hostname:
            try:
                hostname = socket.gethostname()
            except Exception:
                hostname = "localhost"
        return self._send_command(f"HELO {hostname}", "250")

    def login(self, username, password):
        """
        AUTH LOGIN 认证（自动先发送HELO）

        Args:
            username: 邮箱地址
            password: 授权码/密码
        """
        self.helo()
        self._send_command("AUTH LOGIN", "334")
        encoded_user = base64.b64encode(username.encode('utf-8')).decode('ascii')
        self._send_command(encoded_user, "334")
        encoded_pass = base64.b64encode(password.encode('utf-8')).decode('ascii')
        response = self._send_command(encoded_pass, "235")
        if self.debug:
            print("    认证成功")
        return response

    def send_mail(self, sender, recipients, subject, body_text, attachments=None):
        """
        发送一封完整的邮件

        Args:
            sender: 发件人邮箱地址
            recipients: 收件人列表 (list[str])
            subject: 邮件主题
            body_text: 邮件正文
            attachments: 附件列表，每个元素为文件路径字符串 (list[str]|None)

        Returns:
            服务器确认信息
        """
        # (1) MAIL FROM（信封发件人）
        self._send_command(f"MAIL FROM:<{sender}>", "250")

        # (3) RCPT TO（信封收件人，支持多个）
        success_count = 0
        for recipient in recipients:
            try:
                self._send_command(f"RCPT TO:<{recipient}>", "250")
                success_count += 1
            except SMTPError as e:
                if self.debug:
                    print(f"    ⚠ 收件人 {recipient} 被拒绝: {e}")
        if success_count == 0:
            raise SMTPError("所有收件人均被拒绝，无法发送邮件")

        # (4) DATA - 发送邮件内容
        self._send_command("DATA", "354")

        # 构造 RFC 822 格式邮件（首部 + 空行 + 正文 + 附件）
        message = self._build_message(sender, recipients, subject, body_text,
                                      attachments=attachments)

        # SMTP点转义：正文行以"."开头时，额外添加一个"."
        escaped = []
        for line in message.split('\r\n'):
            if line.startswith('.'):
                escaped.append('.' + line)
            else:
                escaped.append(line)
        escaped.append('.')  # 邮件结束标记

        data = '\r\n'.join(escaped) + '\r\n'
        self.writer.sendall(data.encode('utf-8'))
        if self.debug:
            print("    C: (邮件数据已发送)")

        response = self._read_response()
        self._check_response(response, "250")
        return response

    def _build_message(self, sender, recipients, subject, body_text,
                       attachments=None):
        """构造 RFC 822 格式的邮件内容，支持附件"""

        encoded_subject = base64.b64encode(subject.encode('utf-8')).decode('ascii')
        date_str = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800")
        to_header = ", ".join(f"<{r}>" for r in recipients)

        # 如果没有附件，使用简单的单部分格式
        if not attachments:
            lines = []
            lines.append(f"From: <{sender}>")
            lines.append(f"To: {to_header}")
            lines.append(f"Subject: =?UTF-8?B?{encoded_subject}?=")
            lines.append(f"Date: {date_str}")
            lines.append("MIME-Version: 1.0")
            lines.append("Content-Type: text/plain; charset=UTF-8")
            lines.append("Content-Transfer-Encoding: 8bit")
            lines.append("")
            lines.append(body_text)
            return '\r\n'.join(lines)

        # 有附件时使用 multipart/mixed 格式
        boundary = f"==boundary_{id(self)}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}=="

        lines = []
        # 首部
        lines.append(f"From: <{sender}>")
        lines.append(f"To: {to_header}")
        lines.append(f"Subject: =?UTF-8?B?{encoded_subject}?=")
        lines.append(f"Date: {date_str}")
        lines.append("MIME-Version: 1.0")
        lines.append(f'Content-Type: multipart/mixed; boundary="{boundary}"')

        # 正文部分
        lines.append("")
        lines.append(f'--{boundary}')
        lines.append("Content-Type: text/plain; charset=UTF-8")
        lines.append("Content-Transfer-Encoding: 8bit")
        lines.append("")
        lines.append(body_text)

        # 附件部分
        for filepath in attachments:
            filename = os.path.basename(filepath)
            # 猜测MIME类型
            mime_type, _ = mimetypes.guess_type(filepath)
            if not mime_type:
                mime_type = "application/octet-stream"

            # 读取文件并Base64编码
            with open(filepath, 'rb') as f:
                file_data = f.read()
            encoded_data = base64.b64encode(file_data).decode('ascii')

            # RFC 2047 编码文件名以支持中文
            encoded_filename = base64.b64encode(filename.encode('utf-8')).decode('ascii')

            lines.append(f'--{boundary}')
            lines.append(f'Content-Type: {mime_type}; name="=?UTF-8?B?{encoded_filename}?="')
            lines.append("Content-Transfer-Encoding: base64")
            lines.append(f'Content-Disposition: attachment; filename="=?UTF-8?B?{encoded_filename}?="')
            lines.append("")
            # Base64每行76字符
            for i in range(0, len(encoded_data), 76):
                lines.append(encoded_data[i:i + 76])

        # 结束边界
        lines.append(f'--{boundary}--')

        return '\r\n'.join(lines)

    def rset(self):
        """发送RSET命令，复位当前事务"""
        return self._send_command("RSET", "250")

    def vrfy(self, address):
        """发送VRFY命令，验证邮箱地址"""
        return self._send_command(f"VRFY {address}", "250")

    def noop(self):
        """发送NOOP命令，测试连接（RFC 821 规定返回200）"""
        return self._send_command("NOOP", "200")

    def quit(self):
        """发送QUIT命令，结束SMTP会话"""
        try:
            response = self._send_command("QUIT", "221")
        finally:
            self.disconnect()
        return response
