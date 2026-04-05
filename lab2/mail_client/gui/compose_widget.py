"""
写邮件组件 - 填写收件人、主题、正文并发送
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QHBoxLayout,
                              QLineEdit, QTextEdit, QPushButton, QLabel,
                              QMessageBox, QApplication, QFileDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from smtp_client import SMTPClient, SMTPError


class SendMailWorker(QThread):
    """后台发送邮件的线程"""
    success = pyqtSignal()
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, config, recipients, subject, body, attachments=None):
        super().__init__()
        self.config = config
        self.recipients = recipients
        self.subject = subject
        self.body = body
        self.attachments = attachments or []

    def run(self):
        try:
            smtp = SMTPClient(debug=True)
            self.status.emit("正在连接SMTP服务器...")

            if self.config['smtp_ssl']:
                smtp.connect_ssl(self.config['smtp_server'], self.config['smtp_port'])
            else:
                smtp.connect(self.config['smtp_server'], self.config['smtp_port'])

            self.status.emit("正在认证...")
            smtp.login(self.config['email'], self.config['password'])

            self.status.emit("正在发送邮件...")
            smtp.send_mail(self.config['email'], self.recipients,
                           self.subject, self.body, self.attachments)

            smtp.quit()
            self.success.emit()

        except Exception as e:
            self.error.emit(str(e))


class ComposeWidget(QWidget):
    """写邮件组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = None
        self._send_worker = None
        self._attachments = []  # 存储附件文件路径列表
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # ---- 表单 ----
        form = QFormLayout()

        self.to_input = QLineEdit()
        self.to_input.setPlaceholderText("多个收件人用逗号分隔，如: a@b.com, c@d.com")
        form.addRow("收件人:", self.to_input)

        self.subject_input = QLineEdit()
        self.subject_input.setPlaceholderText("邮件主题")
        form.addRow("主题:", self.subject_input)

        layout.addLayout(form)

        # ---- 正文 ----
        self.body_edit = QTextEdit()
        self.body_edit.setPlaceholderText("在此输入邮件正文...")
        self.body_edit.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(self.body_edit)

        # ---- 附件 ----
        att_layout = QHBoxLayout()
        self.add_att_btn = QPushButton("添加附件")
        self.add_att_btn.setStyleSheet(
            "QPushButton { padding: 4px 12px; }")
        self.add_att_btn.clicked.connect(self._add_attachment)
        att_layout.addWidget(self.add_att_btn)

        self.att_label = QLabel("附件: 无")
        self.att_label.setStyleSheet("color: #555;")
        att_layout.addWidget(self.att_label)
        att_layout.addStretch()
        layout.addLayout(att_layout)

        # ---- 按钮 ----
        btn_layout = QHBoxLayout()

        self.send_btn = QPushButton("发送")
        self.send_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; "
            "padding: 8px 24px; font-size: 14px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #45a049; }"
            "QPushButton:disabled { background-color: #aaa; }")
        self.send_btn.clicked.connect(self._on_send)
        btn_layout.addStretch()
        btn_layout.addWidget(self.send_btn)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self._clear_form)
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)

        # ---- 状态 ----
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #555;")
        layout.addWidget(self.status_label)

    def set_config(self, config):
        """设置邮件服务器配置"""
        self._config = config

    def _on_send(self):
        """发送按钮点击"""
        if not self._config:
            QMessageBox.warning(self, "错误", "未配置邮件服务器")
            return

        to_text = self.to_input.text().strip()
        subject = self.subject_input.text().strip()
        body = self.body_edit.toPlainText()

        if not to_text:
            QMessageBox.warning(self, "输入不完整", "请填写收件人地址")
            return
        if not subject:
            QMessageBox.warning(self, "输入不完整", "请填写邮件主题")
            return
        if not body:
            QMessageBox.warning(self, "输入不完整", "请填写邮件正文")
            return

        # 解析收件人列表
        recipients = [r.strip() for r in to_text.split(',') if r.strip()]

        self.send_btn.setEnabled(False)
        self.status_label.setText("正在发送...")
        self.status_label.setStyleSheet("color: blue;")

        # 后台线程发送
        self._send_worker = SendMailWorker(self._config, recipients, subject, body,
                                           self._attachments)
        self._send_worker.success.connect(self._on_send_success)
        self._send_worker.error.connect(self._on_send_error)
        self._send_worker.status.connect(self._on_send_status)
        self._send_worker.start()

    def _on_send_success(self):
        """发送成功"""
        self.send_btn.setEnabled(True)
        self.status_label.setText("邮件发送成功!")
        self.status_label.setStyleSheet("color: green;")
        self.window().statusBar().showMessage("邮件发送成功")
        QMessageBox.information(self, "成功", "邮件已发送!")
        self._clear_form()

    def _on_send_error(self, error_msg):
        """发送失败"""
        self.send_btn.setEnabled(True)
        self.status_label.setText(f"发送失败: {error_msg}")
        self.status_label.setStyleSheet("color: red;")
        QMessageBox.warning(self, "发送失败", error_msg)

    def _on_send_status(self, status):
        """发送状态更新"""
        self.status_label.setText(status)
        self.window().statusBar().showMessage(status)

    def _clear_form(self):
        """清空表单"""
        self.to_input.clear()
        self.subject_input.clear()
        self.body_edit.clear()
        self._attachments = []
        self.att_label.setText("附件: 无")
        self.status_label.setText("")

    def _add_attachment(self):
        """添加附件"""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择附件", "", "所有文件 (*.*)")
        if paths:
            self._attachments.extend(paths)
            # 显示附件信息
            names = [os.path.basename(p) for p in self._attachments]
            self.att_label.setText(f"附件 ({len(names)}个): {', '.join(names)}")
