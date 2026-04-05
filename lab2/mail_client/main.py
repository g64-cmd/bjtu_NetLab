"""
邮件客户端 - 应用入口

启动 PyQt5 GUI，整合 SMTP 发送和 POP3 接收功能。
"""

import sys
import os

# 确保 mail_client 目录在搜索路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont

from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    # 应用程序元信息
    app.setApplicationName("邮件客户端")
    app.setOrganizationName("BJTU NetLab")

    # 全局字体
    app.setFont(QFont("Microsoft YaHei", 9))

    # 全局样式
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f5f5f5;
        }
        QToolBar {
            background-color: #fff;
            border-bottom: 1px solid #ddd;
            padding: 4px;
            spacing: 6px;
        }
        QToolBar QToolButton {
            padding: 6px 12px;
            border-radius: 4px;
        }
        QToolBar QToolButton:hover {
            background-color: #e8e8e8;
        }
        QTabWidget::pane {
            border: 1px solid #ddd;
            background: white;
        }
        QTabBar::tab {
            padding: 8px 20px;
            border: 1px solid #ddd;
            border-bottom: none;
            background: #f0f0f0;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        QTabBar::tab:selected {
            background: white;
            border-bottom: 1px solid white;
        }
        QTableWidget {
            border: none;
            gridline-color: #eee;
        }
        QTableWidget::item:selected {
            background-color: #e3f2fd;
            color: #1565c0;
        }
        QHeaderView::section {
            background-color: #fafafa;
            padding: 6px;
            border: none;
            border-bottom: 1px solid #ddd;
            font-weight: bold;
        }
        QStatusBar {
            background-color: #fff;
            border-top: 1px solid #ddd;
            color: #555;
        }
    """)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
