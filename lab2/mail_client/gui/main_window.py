"""
主窗口 - Tab切换收件箱和写邮件
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (QMainWindow, QWidget, QTabWidget, QToolBar,
                              QAction, QMessageBox, QVBoxLayout, QApplication)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from gui.inbox_widget import InboxWidget
from gui.compose_widget import ComposeWidget
from gui.login_dialog import LoginDialog


class MainWindow(QMainWindow):
    """邮件客户端主窗口"""

    def __init__(self):
        super().__init__()
        self.config = None
        self.pop3 = None
        self._init_ui()
        self._show_login()

    def _init_ui(self):
        self.setWindowTitle("邮件客户端 - SMTP/POP3")
        self.setMinimumSize(1100, 700)
        self.setFont(QFont("Microsoft YaHei", 9))

        # ---- 工具栏 ----
        toolbar = QToolBar("工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.refresh_action = QAction("刷新", self)
        self.refresh_action.triggered.connect(self._refresh_inbox)
        toolbar.addAction(self.refresh_action)

        self.delete_action = QAction("删除", self)
        self.delete_action.triggered.connect(self._delete_mail)
        toolbar.addAction(self.delete_action)

        toolbar.addSeparator()

        self.switch_action = QAction("切换账户", self)
        self.switch_action.triggered.connect(self._switch_account)
        toolbar.addAction(self.switch_action)

        # ---- 中央区域：Tab 切换 ----
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.inbox = InboxWidget()
        self.compose = ComposeWidget()
        self.tabs.addTab(self.inbox, "收件箱")
        self.tabs.addTab(self.compose, "写邮件")
        layout.addWidget(self.tabs)

        # ---- 状态栏 ----
        self.statusBar().showMessage("未连接")

    def _show_login(self):
        """弹出登录对话框"""
        dialog = LoginDialog(self)
        dialog.login_success.connect(self._on_login_success)
        if dialog.exec_() != LoginDialog.Accepted:
            self.close()
            return
        # 如果 dialog 关闭了但没有触发 signal（理论上不会发生）
        if not self.config:
            self.close()

    def _on_login_success(self, config):
        """登录成功回调"""
        self.config = config
        self.pop3 = config['pop3_client']

        self.inbox.set_pop3_client(self.pop3)
        self.inbox.set_config(config)
        self.compose.set_config(config)

        self.statusBar().showMessage(
            f"已连接 - {config['email']} "
            f"(SMTP: {config['smtp_server']}:{config['smtp_port']}, "
            f"POP3: {config['pop3_server']}:{config['pop3_port']})")

        # 自动加载邮件列表
        self._refresh_inbox()

    def _refresh_inbox(self):
        """刷新收件箱"""
        if not self.pop3:
            return
        self.tabs.setCurrentIndex(0)
        self.inbox.load_mails()
        # 同步pop3引用（inbox可能因重连而创建了新实例）
        self.pop3 = self.inbox.pop3

    def _delete_mail(self):
        """删除当前选中的邮件"""
        if self.tabs.currentIndex() == 0:
            self.inbox.delete_selected_mail()

    def _switch_account(self):
        """切换账户"""
        if self.pop3:
            try:
                self.pop3.quit()
            except Exception:
                pass
            self.pop3 = None
        self.config = None
        self.statusBar().showMessage("未连接")
        self._show_login()

    def closeEvent(self, event):
        """窗口关闭时断开POP3连接"""
        # 使用inbox的pop3引用（可能已重连）
        pop3 = self.inbox.pop3 if self.inbox.pop3 else self.pop3
        if pop3:
            try:
                pop3.quit()
            except Exception:
                pass
        event.accept()

    @staticmethod
    def _format_size(size):
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"
