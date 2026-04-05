"""
登录对话框 - 配置SMTP/POP3服务器信息并连接
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
                              QLineEdit, QPushButton, QLabel, QCheckBox,
                              QGroupBox, QMessageBox, QApplication)
from PyQt5.QtCore import pyqtSignal, Qt

from smtp_client import SMTPClient, SMTPError
from pop3_client import POP3Client, POP3Error


class LoginDialog(QDialog):
    """登录对话框 - 输入邮件服务器信息并验证连接"""

    login_success = pyqtSignal(dict)  # 发送配置信息

    # 常用服务器预设
    PRESETS = {
        "QQ邮箱": {
            "smtp_server": "smtp.qq.com", "smtp_port": "465", "smtp_ssl": True,
            "pop3_server": "pop.qq.com", "pop3_port": "995", "pop3_ssl": True,
        },
        "163邮箱": {
            "smtp_server": "smtp.163.com", "smtp_port": "465", "smtp_ssl": True,
            "pop3_server": "pop.163.com", "pop3_port": "995", "pop3_ssl": True,
        },
        "Gmail": {
            "smtp_server": "smtp.gmail.com", "smtp_port": "465", "smtp_ssl": True,
            "pop3_server": "pop.gmail.com", "pop3_port": "995", "pop3_ssl": True,
        },
        "自定义": {},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("邮件客户端 - 登录")
        self.setMinimumWidth(500)
        self._config = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # ---- 预设选择 ----
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("快速选择:"))
        for name in self.PRESETS:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, n=name: self._apply_preset(n))
            preset_layout.addWidget(btn)
        layout.addLayout(preset_layout)

        # ---- 邮箱账户 ----
        account_group = QGroupBox("邮箱账户")
        account_form = QFormLayout(account_group)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("如: yourname@qq.com")
        account_form.addRow("邮箱地址:", self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("授权码（非登录密码）")
        account_form.addRow("授权码:", self.password_input)
        layout.addWidget(account_group)

        # ---- SMTP 服务器设置 ----
        smtp_group = QGroupBox("SMTP 服务器（发送邮件）")
        smtp_form = QFormLayout(smtp_group)
        self.smtp_server_input = QLineEdit()
        self.smtp_server_input.setPlaceholderText("如: smtp.qq.com")
        smtp_form.addRow("服务器:", self.smtp_server_input)

        self.smtp_port_input = QLineEdit("465")
        smtp_form.addRow("端口:", self.smtp_port_input)

        self.smtp_ssl_checkbox = QCheckBox("使用SSL加密")
        self.smtp_ssl_checkbox.setChecked(True)
        smtp_form.addRow("", self.smtp_ssl_checkbox)
        layout.addWidget(smtp_group)

        # ---- POP3 服务器设置 ----
        pop3_group = QGroupBox("POP3 服务器（接收邮件）")
        pop3_form = QFormLayout(pop3_group)
        self.pop3_server_input = QLineEdit()
        self.pop3_server_input.setPlaceholderText("如: pop.qq.com")
        pop3_form.addRow("服务器:", self.pop3_server_input)

        self.pop3_port_input = QLineEdit("995")
        pop3_form.addRow("端口:", self.pop3_port_input)

        self.pop3_ssl_checkbox = QCheckBox("使用SSL加密")
        self.pop3_ssl_checkbox.setChecked(True)
        pop3_form.addRow("", self.pop3_ssl_checkbox)
        layout.addWidget(pop3_group)

        # ---- 按钮 ----
        btn_layout = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self._test_connection)
        btn_layout.addWidget(self.test_btn)

        self.login_btn = QPushButton("登录")
        self.login_btn.setDefault(True)
        self.login_btn.clicked.connect(self._on_login)
        btn_layout.addWidget(self.login_btn)
        layout.addLayout(btn_layout)

        # ---- 状态标签 ----
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _apply_preset(self, name):
        """应用预设服务器配置"""
        preset = self.PRESETS.get(name, {})
        if preset:
            self.smtp_server_input.setText(preset.get("smtp_server", ""))
            self.smtp_port_input.setText(preset.get("smtp_port", "465"))
            self.smtp_ssl_checkbox.setChecked(preset.get("smtp_ssl", True))
            self.pop3_server_input.setText(preset.get("pop3_server", ""))
            self.pop3_port_input.setText(preset.get("pop3_port", "995"))
            self.pop3_ssl_checkbox.setChecked(preset.get("pop3_ssl", True))

    def _gather_config(self):
        """收集所有配置信息"""
        email_addr = self.email_input.text().strip()
        password = self.password_input.text().strip()

        if not email_addr or not password:
            QMessageBox.warning(self, "输入不完整", "请填写邮箱地址和授权码")
            return None

        config = {
            'email': email_addr,
            'password': password,
            'smtp_server': self.smtp_server_input.text().strip(),
            'smtp_port': int(self.smtp_port_input.text().strip() or "465"),
            'smtp_ssl': self.smtp_ssl_checkbox.isChecked(),
            'pop3_server': self.pop3_server_input.text().strip(),
            'pop3_port': int(self.pop3_port_input.text().strip() or "995"),
            'pop3_ssl': self.pop3_ssl_checkbox.isChecked(),
        }

        if not config['smtp_server'] or not config['pop3_server']:
            QMessageBox.warning(self, "输入不完整", "请填写SMTP和POP3服务器地址")
            return None

        return config

    def _test_connection(self):
        """测试SMTP和POP3连接"""
        config = self._gather_config()
        if not config:
            return

        self.status_label.setText("正在测试连接...")
        self.status_label.setStyleSheet("color: blue;")
        QApplication.processEvents()

        results = []

        # 测试 SMTP
        try:
            smtp = SMTPClient(debug=False)
            if config['smtp_ssl']:
                smtp.connect_ssl(config['smtp_server'], config['smtp_port'])
            else:
                smtp.connect(config['smtp_server'], config['smtp_port'])
            smtp.login(config['email'], config['password'])
            smtp.quit()
            results.append("SMTP: 连接成功")
        except Exception as e:
            results.append(f"SMTP: 失败 - {e}")

        # 测试 POP3
        try:
            pop3 = POP3Client(debug=False)
            if config['pop3_ssl']:
                pop3.connect_ssl(config['pop3_server'], config['pop3_port'])
            else:
                pop3.connect(config['pop3_server'], config['pop3_port'])
            pop3.login(config['email'], config['password'])
            pop3.quit()
            results.append("POP3: 连接成功")
        except Exception as e:
            results.append(f"POP3: 失败 - {e}")

        self.status_label.setText("\n".join(results))
        if all("成功" in r for r in results):
            self.status_label.setStyleSheet("color: green;")
        else:
            self.status_label.setStyleSheet("color: red;")

    def _on_login(self):
        """登录按钮点击 - 验证并连接"""
        config = self._gather_config()
        if not config:
            return

        self.status_label.setText("正在连接...")
        self.status_label.setStyleSheet("color: blue;")
        QApplication.processEvents()

        try:
            # 连接 POP3（主连接，保持会话）
            pop3 = POP3Client(debug=False)
            if config['pop3_ssl']:
                pop3.connect_ssl(config['pop3_server'], config['pop3_port'])
            else:
                pop3.connect(config['pop3_server'], config['pop3_port'])
            pop3.login(config['email'], config['password'])

            config['pop3_client'] = pop3
            self._config = config
            self.login_success.emit(config)
            self.accept()

        except Exception as e:
            self.status_label.setText(f"连接失败: {e}")
            self.status_label.setStyleSheet("color: red;")

    def get_config(self):
        return self._config
