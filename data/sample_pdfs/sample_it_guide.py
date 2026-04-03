import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def create_sample_pdf(output_path="data/sample_pdfs/VPN_Setup_Guide.pdf"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    
    section_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=20
    )
    
    body_style = styles['Normal']
    
    story = []
    
    # Page 1
    story.append(Paragraph("Overview", section_style))
    story.append(Paragraph(
        "This is the VPN Setup Guide for employees to enable remote work securely. "
        "The corporate VPN solution ensures encrypted connections between employee devices "
        "and the internal network. All remote employees must install and configure the VPN "
        "client before accessing any internal resources including email, file shares, and "
        "internal web applications.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Please follow all instructions carefully. The VPN encrypts your traffic and ensures "
        "that all data transmitted between your device and the corporate network remains "
        "confidential and secure. Failure to use the VPN when working remotely is a violation "
        "of the corporate security policy and may result in disciplinary action.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "The VPN service is mandatory for all employees who work remotely or access internal "
        "resources from outside the office. This comprehensive guide covers installation, "
        "configuration, troubleshooting, and frequently asked questions. Please read each "
        "section carefully before proceeding to the next step.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Before you begin, ensure you have your corporate credentials and have completed the "
        "security training module in the Learning Management System. Contact IT at extension "
        "4000 if you need your credentials reset or if you have not completed the required "
        "training. Your manager must also approve your remote access request in the HR portal "
        "before you can activate your VPN account.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "System Requirements: Windows 10 or later, macOS 12 or later, 4GB RAM minimum, "
        "stable internet connection with at least 10 Mbps download speed. Corporate-issued "
        "devices come pre-configured with the necessary certificates. If you are using a "
        "personal device, additional steps are required as described in Appendix A.", body_style))
    story.append(PageBreak())
    
    # Page 2
    story.append(Paragraph("Installation", section_style))
    story.append(Paragraph(
        "Step 1: Download the VPN client from the internal portal at https://portal.company.com/vpn. "
        "You will need to authenticate with your corporate credentials to access the download page. "
        "Select the correct version for your operating system.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Step 2: Run the installer with administrator privileges. Right-click the downloaded file "
        "and select 'Run as administrator'. If you are on macOS, drag the application to your "
        "Applications folder and grant the necessary permissions when prompted.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Step 3: Follow the installation wizard. Accept the license agreement and choose the "
        "default installation directory. Do not change the default settings unless instructed "
        "by IT support. The installer will configure the necessary network adapters and "
        "certificates automatically.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Step 4: When prompted, enter the server address: vpn.company.com and your corporate "
        "username. The password field should be left blank during initial setup as it will be "
        "configured during the first connection attempt.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Step 5: After installation, restart your computer to complete the setup process. The "
        "VPN client will appear in your system tray after reboot. Do not attempt to connect "
        "until the restart is complete.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Step 6: To reset your VPN password, navigate to the self-service portal at "
        "https://portal.company.com/reset and click 'Reset Password'. You will receive a "
        "verification code via your registered email address. Enter the code to set your new "
        "password. Passwords must be at least 12 characters and include uppercase, lowercase, "
        "numbers, and special characters.", body_style))
    story.append(PageBreak())
    
    # Page 3
    story.append(Paragraph("Configuration", section_style))
    story.append(Paragraph(
        "Below is a table of common configuration error codes and their resolutions. If you "
        "encounter any of these errors during setup or connection, follow the resolution steps "
        "before contacting IT support.", body_style))
    story.append(Spacer(1, 12))
    
    data = [
        ['Error Code', 'Description', 'Resolution'],
        ['1001', 'Authentication Failed', 'Check your username and password. Ensure CAPS LOCK is off.'],
        ['1002', 'Server Unreachable', 'Verify your internet connection. Try pinging vpn.company.com.'],
        ['1003', 'Certificate Expired', 'Download new certificate from the portal and install it.'],
        ['1004', 'Timeout Error', 'Check firewall settings. Ensure ports 443 and 1194 are open.'],
        ['1005', 'DNS Resolution Failed', 'Use corporate DNS servers: 10.0.0.1 and 10.0.0.2.'],
        ['1006', 'License Limit Reached', 'Wait and retry. Contact IT if the issue persists.'],
        ['1007', 'Protocol Mismatch', 'Update the VPN client to the latest version.'],
        ['1008', 'Split Tunnel Error', 'Disable split tunneling in the client preferences.']
    ]
    t = Table(data, colWidths=[70, 130, 260])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "If you encounter an error code not listed in the table above, please contact the IT "
        "Helpdesk at extension 4000 or email helpdesk@company.com for further assistance. Have "
        "your error code, device serial number, and a screenshot of the error ready when you call. "
        "The average resolution time for VPN issues is 15 minutes during business hours.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Advanced Configuration: For power users who need to configure custom routing rules, "
        "please refer to the Advanced Configuration Guide available on the IT Knowledge Base. "
        "Note that custom configurations must be approved by IT Security before deployment.", body_style))
    story.append(PageBreak())
    
    # Page 4
    story.append(Paragraph("Troubleshooting", section_style))
    story.append(Paragraph(
        "Issue: VPN drops frequently. Solution: Switch to a wired connection. Wireless "
        "connections can be unstable and cause frequent disconnections. If a wired connection is "
        "not available, try moving closer to your Wi-Fi router or switching to a 5GHz network.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Issue: Cannot access internal wiki. Solution: Check your DNS settings. Ensure you are "
        "using the corporate DNS servers (10.0.0.1 and 10.0.0.2). You can verify DNS settings by "
        "running 'ipconfig /all' on Windows or 'scutil --dns' on macOS.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Issue: Slow connection speeds. Solution: Try connecting to a different VPN server. The "
        "nearest server may be overloaded during peak hours (9-11 AM and 2-4 PM). You can change "
        "the server in the VPN client's Settings menu under 'Server Selection'.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Issue: Two-factor authentication not working. Solution: Ensure the Duo Mobile app is up "
        "to date on your smartphone. Clear the app cache if pushes are not arriving. If the issue "
        "persists, request a new authentication token from IT Support.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Issue: VPN client crashes on startup. Solution: Uninstall and reinstall the VPN client. "
        "Make sure your operating system is fully updated before reinstalling. Delete the folder "
        "'C:\\ProgramData\\VPNClient\\config' before reinstallation to clear corrupted settings.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Issue: Cannot connect after OS update. Solution: Major operating system updates can "
        "sometimes break VPN client compatibility. Check the IT portal for the latest VPN client "
        "version compatible with your OS. Download and install the update before attempting to "
        "reconnect.", body_style))
    story.append(PageBreak())
    
    # Page 5
    story.append(Paragraph("FAQ", section_style))
    story.append(Paragraph("Q: Can I use this on my mobile phone?", body_style))
    story.append(Paragraph(
        "A: Yes, download the mobile VPN app from your device's app store. Search for 'Company VPN' "
        "and use the same corporate credentials to log in. Mobile connections have the same security "
        "policies as desktop connections.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Q: Who do I contact for help?", body_style))
    story.append(Paragraph(
        "A: Call the IT Helpdesk at ext 4000 or email helpdesk@company.com. Support is available "
        "Monday through Friday, 8:00 AM to 6:00 PM EST. For urgent issues outside business hours, "
        "use the emergency hotline at ext 4911.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Q: How do I reset my VPN password?", body_style))
    story.append(Paragraph(
        "A: Visit the self-service portal at https://portal.company.com/reset and follow the "
        "instructions. You will need your employee ID and the email registered with your corporate "
        "account. Password resets take effect immediately.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Q: Is split tunneling supported?", body_style))
    story.append(Paragraph(
        "A: No, for security reasons all traffic must route through the VPN when connected. This "
        "ensures that corporate policies are enforced on all network traffic and prevents data "
        "leakage through unsecured channels.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Q: How many devices can I connect simultaneously?", body_style))
    story.append(Paragraph(
        "A: Each employee is allowed up to 3 simultaneous VPN connections across different devices. "
        "If you need additional connections for special purposes, submit a request through the IT "
        "Service Portal with your manager's approval.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Q: What should I do if I suspect my VPN credentials have been compromised?", body_style))
    story.append(Paragraph(
        "A: Immediately change your password through the self-service portal and contact IT Security "
        "at security@company.com. Do not use the VPN until IT Security confirms your account is safe. "
        "If you suspect unauthorized access, also report the incident to your manager.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Q: What are the supported VPN protocols?", body_style))
    story.append(Paragraph(
        "A: We support OpenVPN and IKEv2/IPSec protocols. OpenVPN is recommended for most users as it "
        "provides the best balance of security and performance. IKEv2 is preferred for mobile devices "
        "due to its ability to handle network switching seamlessly. WireGuard support is planned for "
        "Q3 of this year pending security review.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Q: Can I use the VPN from outside the country?", body_style))
    story.append(Paragraph(
        "A: Yes, the VPN can be used internationally. However, please note that some countries may "
        "restrict or monitor VPN usage. Before traveling internationally, notify IT of your destination "
        "and expected travel dates so we can ensure optimal server routing and compliance with local "
        "regulations. Additional security measures may be required for high-risk regions.", body_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Q: How often should I update the VPN client?", body_style))
    story.append(Paragraph(
        "A: The VPN client should be updated promptly when new versions are released. Critical security "
        "updates are pushed automatically. Feature updates are announced via email and on the IT portal. "
        "Running an outdated client version may prevent you from connecting after a certain grace period.", body_style))
    
    doc.build(story)

if __name__ == "__main__":
    create_sample_pdf()

