"""
POP3客户端 - 基于socket手动实现POP3协议（RFC 1939）

支持的POP3命令：USER, PASS, STAT, LIST, RETR, DELE, RSET, NOOP, TOP, UIDL, QUIT
"""

import socket
import ssl
import threading


class POP3Error(Exception):
    """POP3协议错误"""
    pass


class POP3Client:
    """
    POP3客户端 - 通过TCP连接与POP3服务器通信，接收邮件

    用法:
        client = POP3Client()
        client.connect_ssl("pop.qq.com", 995)
        client.login("user@qq.com", "授权码")
        count, size = client.stat()
        mails = client.list()
        raw = client.retr(1)
        client.quit()
    """

    def __init__(self, timeout=15, debug=True):
        self.timeout = timeout
        self.debug = debug
        self.socket = None
        self.reader = None
        self.writer = None
        self._lock = threading.RLock()

    # ========== 连接管理 ==========

    def connect(self, server, port=110):
        """建立明文TCP连接到POP3服务器"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect((server, port))
        self._setup_streams(sock)
        greeting = self._read_line()
        if self.debug:
            print(f"    S: {greeting}")
        self._check_ok(greeting)
        return greeting

    def connect_ssl(self, server, port=995):
        """通过SSL/TLS连接到POP3服务器"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect((server, port))
        context = ssl.create_default_context()
        sock = context.wrap_socket(sock, server_hostname=server)
        self._setup_streams(sock)
        greeting = self._read_line()
        if self.debug:
            print(f"    S: {greeting}")
        self._check_ok(greeting)
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

    def _send_command(self, command):
        """
        发送POP3命令并读取一行响应

        Args:
            command: 要发送的命令字符串

        Returns:
            服务器响应行（包含+OK或-ERR）
        """
        if self.debug:
            print(f"    C: {command}")
        self.writer.sendall((command + "\r\n").encode('utf-8'))
        response = self._read_line()
        if self.debug:
            print(f"    S: {response}")
        self._check_ok(response)
        return response

    def _read_line(self):
        """从服务器读取一行（以CRLF结尾）"""
        line = self.reader.readline()
        if not line:
            raise POP3Error("连接已关闭")
        return line.decode('utf-8', errors='replace').rstrip('\r\n')

    def _read_multiline(self):
        """
        读取多行响应，直到遇到单独一行"."为止

        POP3多行响应以"CRLF.CRLF"结束。
        如果某行以"."开头，需要去除第一个点（点反转义）。
        """
        lines = []
        while True:
            line = self._read_line()
            if line == ".":
                break
            # 点反转义：如果行以"."开头且不是终止行，去除第一个点
            if line.startswith("."):
                line = line[1:]
            lines.append(line)
        return '\r\n'.join(lines)

    def _check_ok(self, response):
        """检查响应是否以+OK开头"""
        if not response.startswith("+OK"):
            raise POP3Error(f"POP3错误: {response}")

    # ========== POP3 命令 ==========

    def login(self, username, password):
        """
        使用USER/PASS命令进行认证

        Args:
            username: 邮箱地址或用户名
            password: 密码或授权码
        """
        with self._lock:
            self._send_command(f"USER {username}")
            response = self._send_command(f"PASS {password}")
            if self.debug:
                print("    认证成功")
            return response

    def stat(self):
        """
        获取邮箱状态

        Returns:
            (邮件数量, 邮箱总字节数) 的元组
        """
        with self._lock:
            response = self._send_command("STAT")
            # 格式: +OK <count> <size>
            parts = response.split()
            count = int(parts[1])
            size = int(parts[2])
            return count, size

    def list(self, msg_num=None):
        """
        列出邮件信息

        Args:
            msg_num: 可选，指定邮件编号。None则列出所有邮件。

        Returns:
            如果指定编号: (编号, 大小) 的元组
            如果不指定: [(编号, 大小), ...] 的列表
        """
        with self._lock:
            if msg_num is not None:
                response = self._send_command(f"LIST {msg_num}")
                parts = response.split()
                return (int(parts[1]), int(parts[2]))
            else:
                self._send_command("LIST")
                data = self._read_multiline()
                result = []
                for line in data.split('\r\n'):
                    if line.strip():
                        parts = line.split()
                        result.append((int(parts[0]), int(parts[1])))
                return result

    def retr(self, msg_num):
        """
        获取指定编号的完整邮件内容

        Args:
            msg_num: 邮件编号（从1开始）

        Returns:
            完整的邮件内容字符串（RFC 822格式）
        """
        with self._lock:
            self._send_command(f"RETR {msg_num}")
            return self._read_multiline()

    def top(self, msg_num, line_count=0):
        """
        获取邮件头部和前N行正文

        Args:
            msg_num: 邮件编号
            line_count: 正文行数（0表示只返回头部）

        Returns:
            邮件头部（+可选正文行）
        """
        with self._lock:
            self._send_command(f"TOP {msg_num} {line_count}")
            return self._read_multiline()

    def dele(self, msg_num):
        """标记指定邮件为删除（在QUIT时生效）"""
        with self._lock:
            return self._send_command(f"DELE {msg_num}")

    def rset(self):
        """撤销所有DELE标记"""
        with self._lock:
            return self._send_command("RSET")

    def noop(self):
        """发送NOOP命令，保持连接"""
        with self._lock:
            return self._send_command("NOOP")

    def uidl(self, msg_num=None):
        """
        获取邮件的唯一标识符

        Args:
            msg_num: 可选，指定编号

        Returns:
            如果指定编号: (编号, uid) 的元组
            如果不指定: [(编号, uid), ...] 的列表
        """
        with self._lock:
            if msg_num is not None:
                response = self._send_command(f"UIDL {msg_num}")
                parts = response.split()
                return (int(parts[1]), parts[2])
            else:
                self._send_command("UIDL")
                data = self._read_multiline()
                result = []
                for line in data.split('\r\n'):
                    if line.strip():
                        parts = line.split()
                        result.append((int(parts[0]), parts[1]))
                return result

    def quit(self):
        """发送QUIT命令，结束会话并提交删除操作"""
        with self._lock:
            try:
                response = self._send_command("QUIT")
            finally:
                self.disconnect()
            return response
