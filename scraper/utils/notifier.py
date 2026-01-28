"""
Email Notifier for HorecaMark.

Sends daily email reports with Excel attachments.
"""

import os
import smtplib
from dataclasses import dataclass
from datetime import date
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from scraper.utils.config import Config
from scraper.utils.logger import get_logger
from scraper.utils.reporter import ReportSummary, ExcelReporter, generate_report

logger = get_logger("notifier")


@dataclass
class EmailConfig:
    """Email configuration settings."""

    smtp_host: str
    smtp_port: int
    username: str
    password: str
    from_addr: str
    to_addrs: list[str]
    use_tls: bool = True


class EmailNotifier:
    """Email notification sender for HorecaMark reports."""

    def __init__(self, config: Optional[EmailConfig] = None):
        """Initialize notifier.

        Args:
            config: Email configuration (default: from Config)
        """
        if config is None:
            config = self._get_config_from_env()

        self.config = config
        self._validate_config()

    @staticmethod
    def _get_config_from_env() -> EmailConfig:
        """Load email configuration from environment.

        Returns:
            EmailConfig with settings from environment variables
        """
        to_addrs_str = Config.EMAIL_TO or ""
        to_addrs = [addr.strip() for addr in to_addrs_str.split(",") if addr.strip()]

        return EmailConfig(
            smtp_host=Config.SMTP_HOST,
            smtp_port=Config.SMTP_PORT,
            username=Config.SMTP_USER,
            password=Config.SMTP_PASSWORD,
            from_addr=Config.EMAIL_FROM,
            to_addrs=to_addrs,
            use_tls=Config.SMTP_PORT == 587,
        )

    def _validate_config(self) -> None:
        """Validate email configuration.

        Raises:
            ValueError: If required configuration is missing
        """
        if not self.config.username:
            raise ValueError("SMTP_USER environment variable is required")
        if not self.config.password:
            raise ValueError("SMTP_PASSWORD environment variable is required")
        if not self.config.from_addr:
            raise ValueError("EMAIL_FROM environment variable is required")
        if not self.config.to_addrs:
            raise ValueError("EMAIL_TO environment variable is required")

    def send_email(
        self,
        subject: str,
        body: str,
        attachments: Optional[list[Path]] = None,
        html: bool = False,
    ) -> bool:
        """Send email with optional attachments.

        Args:
            subject: Email subject
            body: Email body text
            attachments: List of file paths to attach
            html: Whether body is HTML format

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = self.config.from_addr
            msg["To"] = ", ".join(self.config.to_addrs)
            msg["Subject"] = subject

            # Attach body
            content_type = "html" if html else "plain"
            msg.attach(MIMEText(body, content_type, _charset="utf-8"))

            # Attach files
            if attachments:
                for filepath in attachments:
                    if not filepath.exists():
                        logger.warning(f"Attachment not found: {filepath}")
                        continue

                    with open(filepath, "rb") as f:
                        part = MIMEApplication(f.read(), Name=filepath.name)

                    part["Content-Disposition"] = f'attachment; filename="{filepath.name}"'
                    msg.attach(part)

            # Send email
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.use_tls:
                    server.starttls()

                server.login(self.config.username, self.config.password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {self.config.to_addrs}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return False

        except smtplib.SMTPException as e:
            logger.error(f"SMTP error occurred: {e}")
            return False

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_report(
        self,
        report_path: Path,
        summary: ReportSummary,
        critical_changes: Optional[list[dict]] = None,
    ) -> bool:
        """Send daily report email with Excel attachment.

        Args:
            report_path: Path to Excel report file
            summary: Report summary statistics
            critical_changes: List of critical changes to highlight

        Returns:
            True if sent successfully, False otherwise
        """
        subject = f"[HorecaMark] Gunluk Fiyat Raporu - {summary.date.strftime('%d.%m.%Y')}"

        # Build email body
        critical_section = self._build_critical_section(critical_changes or [])

        body = self._get_email_template(summary, critical_section)

        return self.send_email(
            subject=subject,
            body=body,
            attachments=[report_path],
        )

    def _build_critical_section(self, critical_changes: list[dict]) -> str:
        """Build critical changes section for email.

        Args:
            critical_changes: List of critical change dicts

        Returns:
            Formatted HTML string
        """
        if not critical_changes:
            return "<p>Kritik degisiklik yok.</p>"

        rows = []
        for change in critical_changes[:10]:  # Max 10 items
            row = f"""
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 8px;">{change.get('product_name', '-')}</td>
                <td style="padding: 8px;">{change.get('site_name', '-')}</td>
                <td style="padding: 8px; text-align: right;">{change.get('old_price', 0):.2f} TL</td>
                <td style="padding: 8px; text-align: right;">{change.get('new_price', 0):.2f} TL</td>
                <td style="padding: 8px; text-align: right; color: {'red' if change.get('change_percent', 0) < 0 else 'green'};">
                    {change.get('change_percent', 0):.1f}%
                </td>
            </tr>
            """
            rows.append(row)

        return f"""
        <table style="border-collapse: collapse; width: 100%; max-width: 600px; margin: 15px 0;">
            <thead>
                <tr style="background-color: #4472C4; color: white;">
                    <th style="padding: 10px; text-align: left;">Urun</th>
                    <th style="padding: 10px; text-align: left;">Site</th>
                    <th style="padding: 10px; text-align: right;">Eski</th>
                    <th style="padding: 10px; text-align: right;">Yeni</th>
                    <th style="padding: 10px; text-align: right;">Degisim</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
        """

    def _get_email_template(self, summary: ReportSummary, critical_section: str) -> str:
        """Get HTML email template.

        Args:
            summary: Report summary statistics
            critical_section: Critical changes HTML section

        Returns:
            Complete HTML email body
        """
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #4472C4; color: white; padding: 15px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 20px; }}
        .summary {{ background-color: #f5f5f5; padding: 15px; margin: 15px 0; border-radius: 5px; }}
        .summary-row {{ display: flex; justify-content: space-between; padding: 5px 0; }}
        .summary-label {{ font-weight: bold; }}
        .stat-box {{ display: inline-block; background-color: white; padding: 10px 15px; margin: 5px; border-radius: 5px; text-align: center; min-width: 100px; }}
        .stat-value {{ font-size: 20px; font-weight: bold; color: #4472C4; }}
        .stat-label {{ font-size: 12px; color: #666; }}
        .critical {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 15px 0; }}
        .footer {{ text-align: center; padding: 15px; color: #666; font-size: 12px; }}
        .alert-red {{ color: #dc3545; }}
        .alert-green {{ color: #28a745; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>HORECAMARK GUNLUK FIYAT ISTIHBARAT RAPORU</h1>
        </div>

        <p>Sayin Yetkili,</p>
        <p>Gunluk fiyat istihbarat raporunuz asagidadir.</p>

        <div class="summary">
            <h3 style="margin-top: 0;">OZET BILGILER</h3>
            <div class="stat-box">
                <div class="stat-value">{summary.total_products}</div>
                <div class="stat-label">Toplam Urun</div>
            </div>
            <div class="stat-box">
                <div class="stat-value alert-red">{summary.price_decreases}</div>
                <div class="stat-label">Fiyat Dustu</div>
            </div>
            <div class="stat-box">
                <div class="stat-value alert-green">{summary.price_increases}</div>
                <div class="stat-label">Fiyat Artti</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{summary.stock_changes}</div>
                <div class="stat-label">Stok Degisikligi</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{summary.new_products}</div>
                <div class="stat-label">Yeni Urun</div>
            </div>
        </div>

        <div class="critical">
            <h3 style="margin-top: 0;">KRITIK DEGISIKLIKLER</h3>
            {critical_section}
        </div>

        <p>Detayli rapor ekteki Excel dosyasindadir.</p>

        <div class="footer">
            <p>Bu e-posta otomatik olarak gonderilmistir.</p>
            <p>HorecaMark Price Bot &copy; {summary.date.year}</p>
        </div>
    </div>
</body>
</html>
        """

    def send_test_email(self) -> bool:
        """Send a test email to verify configuration.

        Returns:
            True if sent successfully
        """
        subject = "[HorecaMark] Test E-postasi"
        body = """
        <html>
        <body>
            <h2>HorecaMark Email Test</h2>
            <p>Email konfigurasyonu basarili!</p>
            <p>Gunluk raporlar bu adrese gonderilecektir.</p>
        </body>
        </html>
        """

        return self.send_email(subject, body, html=True)

    def is_configured(self) -> bool:
        """Check if email is properly configured.

        Returns:
            True if all required settings are present
        """
        return all([
            self.config.username,
            self.config.password,
            self.config.from_addr,
            self.config.to_addrs,
        ])


def send_report_email(
    report_path: Optional[Path] = None,
    report_date: Optional[date] = None,
) -> bool:
    """Convenience function to send daily report email.

    Args:
        report_path: Path to report file (generates if None)
        report_date: Date for report (default: today)

    Returns:
        True if sent successfully
    """
    # Check configuration first
    notifier = EmailNotifier()

    if not notifier.is_configured():
        logger.error("Email not configured. Set SMTP_USER, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO.")
        return False

    # Generate report if not provided
    if report_path is None:
        reporter = ExcelReporter()
        session = reporter._generate_summary.__code__.co_consts[1]  # Get session reference

    reporter = ExcelReporter()
    from scraper.database import get_session

    session = get_session()
    try:
        summary = reporter._generate_summary(session, report_date or date.today())

        if report_path is None:
            report_path = reporter.generate_daily_report(report_date, session)

        # Get critical changes for email
        from scraper.utils.analyzer import _get_action_items
        from datetime import datetime, timedelta

        day_start = datetime.combine((report_date or date.today()), datetime.min.time())
        day_end = day_start + timedelta(days=1)

        critical_changes = _get_action_items(session, day_start, day_end)

        return notifier.send_report(report_path, summary, critical_changes)

    finally:
        session.close()


def send_simple_report(report_date: Optional[date] = None) -> bool:
    """Send simple report email without complex processing.

    Args:
        report_date: Date for report (default: today)

    Returns:
        True if sent successfully
    """
    return send_report_email(report_date=report_date)


if __name__ == "__main__":
    # Send test email
    print("Sending test email...")
    notifier = EmailNotifier()
    if notifier.is_configured():
        success = notifier.send_test_email()
        print(f"Test email {'sent' if success else 'failed'}")
    else:
        print("Email not configured. Please set environment variables:")
        print("  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD")
        print("  EMAIL_FROM, EMAIL_TO")
