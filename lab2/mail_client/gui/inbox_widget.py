"""
收件箱组件 - 邮件列表 + 邮件内容查看
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
                              QTableWidget, QTableWidgetItem, QHeaderView,
                              QLabel, QFrame, QTextBrowser, QPushButton,
                              QMessageBox, QFileDialog, QApplication)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QColor

from mail_parser import MailParser


def _format_size(size):
    """格式化文件大小"""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


class MailListWorker(QThread):
    """后台加载邮件列表的线程"""
    progress = pyqtSignal(int, int)          # current, total
    mail_header = pyqtSignal(int, dict)      # msg_num, parsed_header
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, pop3_client, mail_count):
        super().__init__()
        self.pop3 = pop3_client
        self.mail_count = mail_count

    def run(self):
        for i in range(1, self.mail_count + 1):
            try:
                header_raw = self.pop3.top(i, 0)
                parsed = MailParser.parse(header_raw)
                parsed['_msg_num'] = i
                self.mail_header.emit(i, parsed)
                self.progress.emit(i, self.mail_count)
            except Exception as e:
                self.error.emit(f"加载邮件 {i} 失败: {e}")
        self.finished.emit()


class MailContentWorker(QThread):
    """后台加载单封邮件内容的线程"""
    loaded = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, pop3_client, msg_num):
        super().__init__()
        self.pop3 = pop3_client
        self.msg_num = msg_num

    def run(self):
        try:
            raw = self.pop3.retr(self.msg_num)
            parsed = MailParser.parse(raw)
            parsed['_msg_num'] = self.msg_num
            self.loaded.emit(parsed)
        except Exception as e:
            self.error.emit(f"获取邮件内容失败: {e}")


class InboxWidget(QWidget):
    """收件箱组件 - 左侧邮件列表 + 右侧邮件查看"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pop3 = None
        self._config = None
        self.mail_count = 0
        self._list_worker = None
        self._content_worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)

        # ---- 左侧：邮件列表 ----
        list_frame = QFrame()
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(0, 0, 0, 0)

        self.mail_table = QTableWidget(0, 4)
        self.mail_table.setHorizontalHeaderLabels(["序号", "发件人", "主题", "日期"])
        self.mail_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.mail_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.mail_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.mail_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.mail_table.currentCellChanged.connect(self._on_mail_selected)
        list_layout.addWidget(self.mail_table)

        splitter.addWidget(list_frame)

        # ---- 右侧：邮件查看 ----
        view_frame = QFrame()
        view_layout = QVBoxLayout(view_frame)
        view_layout.setContentsMargins(5, 5, 5, 5)

        # 邮件头部信息
        self.subject_label = QLabel("(选择一封邮件查看)")
        self.subject_label.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        self.subject_label.setWordWrap(True)
        view_layout.addWidget(self.subject_label)

        info_layout = QHBoxLayout()
        self.from_label = QLabel("发件人: ")
        self.from_label.setStyleSheet("color: #555;")
        self.date_label = QLabel("日期: ")
        self.date_label.setStyleSheet("color: #555;")
        self.to_label = QLabel("收件人: ")
        self.to_label.setStyleSheet("color: #555;")
        info_layout.addWidget(self.from_label)
        info_layout.addWidget(self.date_label)
        info_layout.addWidget(self.to_label)
        info_layout.addStretch()
        view_layout.addLayout(info_layout)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #ccc;")
        view_layout.addWidget(line)

        # 邮件正文
        self.body_browser = QTextBrowser()
        self.body_browser.setOpenExternalLinks(True)
        self.body_browser.setFont(QFont("Microsoft YaHei", 10))
        view_layout.addWidget(self.body_browser)

        # 附件区域
        self.attachment_frame = QFrame()
        self.attachment_layout = QHBoxLayout(self.attachment_frame)
        self.attachment_layout.setContentsMargins(0, 2, 0, 2)
        self.attachment_label = QLabel("附件: 无")
        self.attachment_layout.addWidget(self.attachment_label)
        self.attachment_layout.addStretch()
        view_layout.addWidget(self.attachment_frame)

        # 底部操作按钮
        bottom_layout = QHBoxLayout()
        self.delete_btn = QPushButton("删除此邮件")
        self.delete_btn.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white; "
            "padding: 6px 16px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #d32f2f; }")
        self.delete_btn.clicked.connect(self.delete_selected_mail)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.delete_btn)
        view_layout.addLayout(bottom_layout)

        splitter.addWidget(view_frame)
        splitter.setSizes([300, 500])
        layout.addWidget(splitter)

    def set_pop3_client(self, pop3_client):
        """设置POP3客户端实例"""
        self.pop3 = pop3_client

    def set_config(self, config):
        """保存配置信息用于重连"""
        self._config = config

    def load_mails(self):
        """加载邮件列表"""
        if not self.pop3:
            return

        # 尝试获取邮箱状态，如果连接断开则自动重连
        try:
            self.mail_count, mailbox_size = self.pop3.stat()
        except Exception:
            # 连接可能已断开，尝试重连
            if not self._reconnect():
                return
            try:
                self.mail_count, mailbox_size = self.pop3.stat()
            except Exception as e:
                QMessageBox.warning(self, "错误", f"获取邮箱状态失败: {e}")
                return

        # 清空表格
        self.mail_table.setRowCount(0)

        # 显示邮箱状态信息
        self.window().statusBar().showMessage(
            f"邮箱状态: {self.mail_count} 封邮件, 总大小 {_format_size(mailbox_size)}")

        # 启动后台线程加载邮件列表
        self._list_worker = MailListWorker(self.pop3, self.mail_count)
        self._list_worker.mail_header.connect(self._add_mail_row)
        self._list_worker.progress.connect(self._on_load_progress)
        self._list_worker.error.connect(self._on_load_error)
        self._list_worker.start()

    def _reconnect(self):
        """POP3连接断开时自动重连"""
        if not self._config:
            QMessageBox.warning(self, "连接断开", "POP3连接已断开，且缺少配置信息无法重连")
            return False

        self.window().statusBar().showMessage("POP3连接已断开，正在重新连接...")
        QApplication.processEvents()

        try:
            from pop3_client import POP3Client
            pop3 = POP3Client(debug=False)
            if self._config['pop3_ssl']:
                pop3.connect_ssl(self._config['pop3_server'], self._config['pop3_port'])
            else:
                pop3.connect(self._config['pop3_server'], self._config['pop3_port'])
            pop3.login(self._config['email'], self._config['password'])

            self.pop3 = pop3
            self.window().statusBar().showMessage("POP3重连成功")
            return True
        except Exception as e:
            QMessageBox.warning(self, "重连失败", f"POP3重连失败: {e}")
            return False

    def _add_mail_row(self, msg_num, parsed):
        """在表格中添加一行邮件"""
        row = self.mail_table.rowCount()
        self.mail_table.insertRow(row)
        self.mail_table.setItem(row, 0, QTableWidgetItem(str(msg_num)))
        self.mail_table.setItem(row, 1, QTableWidgetItem(
            parsed.get('from_name') or parsed.get('from_addr', '')))
        self.mail_table.setItem(row, 2, QTableWidgetItem(
            parsed.get('subject', '(无主题)')))
        self.mail_table.setItem(row, 3, QTableWidgetItem(
            parsed.get('date', '')))
        # 存储msg_num到第一列的data中
        self.mail_table.item(row, 0).setData(Qt.UserRole, msg_num)

    def _on_load_progress(self, current, total):
        """加载进度"""
        self.window().statusBar().showMessage(f"正在加载邮件列表... {current}/{total}")

    def _on_load_error(self, error_msg):
        """加载错误"""
        print(error_msg)

    def _on_mail_selected(self, row, col, prev_row, prev_col):
        """选中某封邮件时，加载并显示完整内容"""
        if row < 0:
            return

        item = self.mail_table.item(row, 0)
        if not item:
            return
        msg_num = item.data(Qt.UserRole)

        # 清空当前显示
        self.subject_label.setText("加载中...")
        self.body_browser.setHtml("<p style='color:#888;'>正在获取邮件内容...</p>")

        # 后台线程获取邮件内容
        self._content_worker = MailContentWorker(self.pop3, msg_num)
        self._content_worker.loaded.connect(self._display_mail)
        self._content_worker.error.connect(self._on_content_error)
        self._content_worker.start()

    @pyqtSlot(dict)
    def _display_mail(self, mail_data):
        """显示解析后的邮件"""
        self.subject_label.setText(mail_data.get('subject', '(无主题)'))
        self.from_label.setText(f"发件人: {mail_data.get('from_name', '')} <{mail_data.get('from_addr', '')}>")
        self.to_label.setText(f"收件人: {mail_data.get('to', '')}")
        self.date_label.setText(f"日期: {mail_data.get('date', '')}")

        # 显示正文（优先HTML，其次纯文本）
        body_html = mail_data.get('body_html', '')
        body_text = mail_data.get('body_text', '')

        if body_html:
            self.body_browser.setHtml(body_html)
        elif body_text:
            self.body_browser.setPlainText(body_text)
        else:
            self.body_browser.setPlainText("(邮件正文为空)")

        # 显示附件
        self._clear_attachment_buttons()
        attachments = mail_data.get('attachments', [])
        if attachments:
            self.attachment_label.setText(f"附件 ({len(attachments)}个):")
            for att in attachments:
                btn = QPushButton(f"{att['filename']} ({_format_size(att['size'])})")
                btn.setStyleSheet("padding: 2px 8px;")
                btn.clicked.connect(lambda checked, a=att: self._save_attachment(a))
                self.attachment_layout.insertWidget(
                    self.attachment_layout.count() - 1, btn)
        else:
            self.attachment_label.setText("附件: 无")

        self.window().statusBar().showMessage(
            f"已加载邮件: {mail_data.get('subject', '')}")

    def _on_content_error(self, error_msg):
        """内容加载失败"""
        self.subject_label.setText("加载失败")
        self.body_browser.setHtml(f"<p style='color:red;'>{error_msg}</p>")

    def delete_selected_mail(self):
        """删除选中的邮件"""
        row = self.mail_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一封邮件")
            return

        item = self.mail_table.item(row, 0)
        msg_num = item.data(Qt.UserRole)
        subject = self.mail_table.item(row, 2).text()

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除邮件 \"{subject}\" 吗？\n（删除将在断开连接时生效）",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                self.pop3.dele(msg_num)
                self.mail_table.removeRow(row)
                self.subject_label.setText("(选择一封邮件查看)")
                self.body_browser.clear()
                self.from_label.setText("发件人: ")
                self.to_label.setText("收件人: ")
                self.date_label.setText("日期: ")
                self._clear_attachment_buttons()
                self.attachment_label.setText("附件: 无")
                self.window().statusBar().showMessage(f"邮件已标记删除: {subject}")
            except Exception as e:
                QMessageBox.warning(self, "删除失败", str(e))

    def _clear_attachment_buttons(self):
        """清除附件按钮"""
        # 保留 attachment_label 和 stretch，删除其余按钮
        while self.attachment_layout.count() > 2:
            item = self.attachment_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

    def _save_attachment(self, attachment):
        """保存附件到文件"""
        filename = attachment['filename']
        data = attachment['data']

        path, _ = QFileDialog.getSaveFileName(
            self, "保存附件", filename, "所有文件 (*.*)")
        if path:
            try:
                with open(path, 'wb') as f:
                    f.write(data)
                QMessageBox.information(self, "保存成功", f"附件已保存到:\n{path}")
            except Exception as e:
                QMessageBox.warning(self, "保存失败", str(e))
