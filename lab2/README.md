# Lab 2: SMTP/POP3 Email Client

## Objective

Implement an Email client using Python with SMTP and POP3 protocols. The application provides a PyQt5 GUI for sending and receiving emails.

## Project Structure

```
lab2/
├── mail_client/
│   ├── smtp_client.py             # SMTP client (raw socket implementation)
│   ├── pop3_client.py             # POP3 client (raw socket implementation)
│   ├── mail_parser.py             # MIME email parser
│   ├── main.py                    # Application entry point
│   └── gui/
│       ├── __init__.py
│       ├── login_dialog.py        # Login dialog
│       ├── main_window.py         # Main window (tab-based inbox/compose)
│       ├── inbox_widget.py        # Inbox widget
│       └── compose_widget.py      # Compose email widget
└── README.md
```

## Features

**SMTP Sending:**
- SSL/TLS encrypted connection
- AUTH LOGIN authentication
- Multiple recipients support
- Chinese subject encoding (MIME Base64)
- SMTP dot-stuffing

**POP3 Receiving:**
- SSL/TLS encrypted connection
- USER/PASS authentication
- Mailbox status query (STAT)
- Mail listing (TOP command for headers)
- Full email retrieval (RETR command)
- Email deletion (DELE command)
- Attachment saving

**GUI:**
- PyQt5 visual interface
- Login dialog with presets (QQ Mail / 163 / Gmail)
- Tab navigation: Inbox / Compose
- Background thread loading (non-blocking UI)
- Email list table with content viewer
- Attachment download

## Supported POP3 Commands (RFC 1939)

| Command | Description |
|---------|-------------|
| USER | Send username |
| PASS | Send password |
| STAT | Get mailbox status (message count and size) |
| LIST | List message info |
| RETR | Retrieve full message content |
| TOP | Retrieve message header and first N lines |
| DELE | Mark message for deletion |
| RSET | Undo all DELE marks |
| NOOP | Keep connection alive |
| UIDL | Get message unique identifier |
| QUIT | End session |

## Requirements

- Python 3.x
- PyQt5

## Running

```bash
cd lab2
python mail_client/main.py
```

## Usage

1. Run `main.py` — a login dialog appears
2. Select an email preset (QQ Mail / 163 / Gmail) or enter server info manually
3. Enter your email address and authorization code
4. Click "Test Connection" to verify server connectivity
5. Click "Login" to enter the main interface
6. **Inbox**: Browse emails, click to view content, delete emails, save attachments
7. **Compose**: Fill in recipients, subject, body, and click Send

## Notes

- Both SMTP and POP3 protocols are implemented using raw Python sockets (no smtplib/poplib)
- Use your email authorization code, not your login password
- Deleted emails are removed upon QUIT
