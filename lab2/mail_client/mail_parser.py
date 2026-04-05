"""
邮件解析工具 - 将原始RFC 822邮件文本解析为结构化数据

使用Python标准库 email 解析MIME邮件，支持：
- 中文头部解码（Base64 / Quoted-Printable）
- multipart邮件（纯文本 + HTML + 附件）
- 附件提取
"""

import email
from email.header import decode_header
from email.utils import parseaddr


class MailParser:
    """邮件解析器 - 将RETR返回的原始邮件解析为可显示的结构化数据"""

    @staticmethod
    def parse(raw_mail):
        """
        解析原始邮件为结构化字典

        Args:
            raw_mail: RETR/TOP命令返回的原始邮件文本

        Returns:
            dict: 包含 from_name, from_addr, to, subject, date,
                  body_text, body_html, attachments 的字典
        """
        if isinstance(raw_mail, str):
            raw_bytes = raw_mail.encode('utf-8', errors='replace')
        else:
            raw_bytes = raw_mail

        msg = email.message_from_bytes(raw_bytes)

        # 解析发件人
        from_header = msg.get('From', '')
        from_name, from_addr = parseaddr(from_header)
        from_name = MailParser.decode_header_value(from_name)

        # 解析收件人
        to_header = msg.get('To', '')
        to_decoded = MailParser.decode_header_value(to_header)

        # 解析主题
        subject = MailParser.decode_header_value(msg.get('Subject', ''))

        # 日期
        date_str = msg.get('Date', '')

        # 提取正文和附件
        body_text, body_html, attachments = MailParser._extract_parts(msg)

        return {
            'from_name': from_name,
            'from_addr': from_addr,
            'to': to_decoded,
            'subject': subject,
            'date': date_str,
            'body_text': body_text,
            'body_html': body_html,
            'attachments': attachments,
        }

    @staticmethod
    def decode_header_value(header_value):
        """
        解码邮件头部字段值

        处理 =?UTF-8?B?...?= (Base64) 和 =?UTF-8?Q?...?= (Quoted-Printable) 编码
        """
        if not header_value:
            return ''

        try:
            parts = decode_header(header_value)
        except Exception:
            return str(header_value)

        decoded_parts = []
        for part, charset in parts:
            if isinstance(part, bytes):
                try:
                    decoded_parts.append(part.decode(charset or 'utf-8', errors='replace'))
                except (LookupError, UnicodeDecodeError):
                    decoded_parts.append(part.decode('utf-8', errors='replace'))
            else:
                decoded_parts.append(part)

        return ''.join(decoded_parts)

    @staticmethod
    def _extract_parts(msg):
        """
        从邮件消息对象中提取正文和附件

        Returns:
            (body_text, body_html, attachments) 元组
        """
        body_text = ''
        body_html = ''
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get('Content-Disposition', ''))

                # 附件处理
                if 'attachment' in disposition:
                    payload = part.get_payload(decode=True)
                    if payload:
                        filename = part.get_filename()
                        if filename:
                            filename = MailParser.decode_header_value(filename)
                        else:
                            filename = 'attachment'
                        attachments.append({
                            'filename': filename,
                            'content_type': content_type,
                            'data': payload,
                            'size': len(payload),
                        })
                    continue

                # 纯文本正文
                if content_type == 'text/plain':
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        try:
                            body_text = payload.decode(charset, errors='replace')
                        except LookupError:
                            body_text = payload.decode('utf-8', errors='replace')

                # HTML正文
                elif content_type == 'text/html':
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        try:
                            body_html = payload.decode(charset, errors='replace')
                        except LookupError:
                            body_html = payload.decode('utf-8', errors='replace')
        else:
            # 非multipart邮件，直接提取正文
            content_type = msg.get_content_type()
            disposition = str(msg.get('Content-Disposition', ''))

            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                try:
                    decoded = payload.decode(charset, errors='replace')
                except LookupError:
                    decoded = payload.decode('utf-8', errors='replace')

                if content_type == 'text/html':
                    body_html = decoded
                else:
                    body_text = decoded

            # 检查是否有文件名（单部分附件）
            filename = msg.get_filename()
            if filename and payload and 'attachment' in disposition:
                filename = MailParser.decode_header_value(filename)
                attachments.append({
                    'filename': filename,
                    'content_type': content_type,
                    'data': payload,
                    'size': len(payload),
                })

        return body_text, body_html, attachments
