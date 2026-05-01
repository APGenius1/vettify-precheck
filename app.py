# ================= ELITE INTELLIGENCE REPORT - COMPLETE =================

def generate_intelligence_report(client_data):
    """
    Generate elite perception intelligence report - 3+ pages of actionable strategic intelligence
    Designed for high-net-worth individuals, founders raising capital, and public figures
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, 
                           topMargin=72, bottomMargin=72, 
                           leftMargin=72, rightMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    # ========== CUSTOM STYLES ==========
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=26, textColor=colors.HexColor('#0a1628'), alignment=1, spaceAfter=6, fontName='Helvetica-Bold')
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#8a9bb0'), alignment=1, spaceAfter=20)
    section_header = ParagraphStyle('SectionHeader', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#0a1628'), spaceAfter=12, spaceBefore=20, fontName='Helvetica-Bold')
    subsection = ParagraphStyle('Subsection', parent=styles['Heading3'], fontSize=12, textColor=colors.HexColor('#0a1628'), spaceAfter=8, spaceBefore=12, fontName='Helvetica-Bold')
    gold_header = ParagraphStyle('GoldHeader', parent=styles['Heading3'], fontSize=11, textColor=colors.HexColor('#c9a03d'), spaceAfter=6, spaceBefore=10, fontName='Helvetica-Bold')
    body_text = ParagraphStyle('BodyText', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#2c3e50'), spaceAfter=8, leading=16)
    insight_text = ParagraphStyle('InsightText', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#c9a03d'), spaceAfter=8, leading=16, fontName='Helvetica-Oblique')
    risk_text = ParagraphStyle('RiskText', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#8a9bb0'), spaceAfter=6, leading=14)
    bullet = ParagraphStyle('Bullet', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#2c3e50'), spaceAfter=4, leftIndent=12, bulletIndent=0)
    small_text = ParagraphStyle('SmallText', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#8a9bb0'), spaceAfter=4, leading=12)
    
    # Generate a perception score (for demo, based on input params if provided)
    perception_score = 74
    authority_score = 68
    narrative_score = 71
    visibility_score = 59
    
    # ========== PAGE 1 ==========
    # Header
    story.append(Paragraph("CONFIDENTIAL", ParagraphStyle('Confidential', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#c9a03d'), alignment=2, spaceAfter=6)))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("VETTIFY INTELLIGENCE", title_style))
    story.append(Paragraph("Private Perception & Authority Briefing", subtitle_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#c9a03d')))
    story.append(Spacer(1, 0.2*inch))
    
    # Prepared for line
    client_name = client_data.get('full_name', 'Private Client')
    story.append(Paragraph(f"Prepared for: <b>{client_name}</b>", body_text))
    story.append(Paragraph(f"Date: {datetime.now().strftime('%d %B %Y')}", body_text))
    story.append(Paragraph("Classification: Private & Confidential", body_text))
    story.append(Spacer(1, 0.15*inch))
    
    # EXECUTIVE SUMMARY
    story.append(Paragraph("I. EXECUTIVE SUMMARY", section_header))
    story.append(Paragraph(
        "This briefing evaluates how your public presence is currently interpreted by high-stakes audiences — investors, media, strategic partners, and institutional decision-makers.",
        body_text
    ))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(
        "The analysis identifies perception gaps that may be constraining opportunity flow, reputation leverage, and trust velocity in elite environments.",
        body_text
    ))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(
        "<b>Key finding:</b> Your current positioning communicates competence but not dominance. The gap between actual capability and perceived authority is creating hidden friction in high-trust interactions.",
        insight_text
    ))
    story.append(Spacer(1, 0.1*inch))
    
    # PERCEPTION INDEX
    story.append(Paragraph("II. PERCEPTION INDEX", section_header))
    
    # Main score box (simulated gauge)
    story.append(Paragraph(f"<b>Overall Perception Score: {perception_score} / 100</b>", ParagraphStyle('Score', parent=styles['Normal'], fontSize=22, textColor=colors.HexColor('#c9a03d'), spaceAfter=6)))
    story.append(Paragraph("Classification: <b>Controlled but Fragile Authority Signal</b>", insight_text))
    story.append(Spacer(1, 0.05*inch))
    
    # Sub-scores table
    score_data = [
        ["Authority Positioning", f"{authority_score}/100", "Weak Consistency"],
        ["Narrative Alignment", f"{narrative_score}/100", "Fragmented Signal"],
        ["Visibility Footprint", f"{visibility_score}/100", "Under-Optimised"],
    ]
    score_table = Table(score_data, colWidths=[2.2*inch, 1.2*inch, 2.2*inch])
    score_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0a1628')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph(
        "Your authority signals are not yet reinforced by consistent narrative or third-party validation. This creates a perception gap where actual capability exceeds perceived weight in high-stakes rooms.",
        body_text
    ))
    story.append(Spacer(1, 0.15*inch))
    
    # ========== PAGE 2 ==========
    story.append(Paragraph("III. CREDIBILITY SIGNAL INTELLIGENCE", section_header))
    
    story.append(Paragraph("A. Authority Positioning Analysis", subsection))
    story.append(Paragraph(
        "Your public-facing identity does not consistently signal decision-making power. In environments where first impressions determine access (investor intros, board consideration, media features), weak authority signals create filtering friction.",
        body_text
    ))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(
        "Current signals: Competence-focused, contribution-oriented, collaborative tone.",
        body_text
    ))
    story.append(Paragraph(
        "Missing signals: Decisiveness, domain ownership, directional influence, gatekeeper positioning.",
        body_text
    ))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(
        "<b>Interpretation risk:</b> You are likely being categorized as 'operator' rather than 'owner,' 'contributor' rather than 'authority.' In high-stakes contexts, this reduces perceived strategic weight.",
        risk_text
    ))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("B. Narrative Alignment Audit", subsection))
    story.append(Paragraph(
        "Across your public platforms, your narrative does not form a single, unified identity axis. This forces external observers to 'interpret' you rather than immediately understand your positioning.",
        body_text
    ))
    story.append(Spacer(1, 0.05*inch))
    
    # Consistency breakdown
    story.append(Paragraph("<b>Platform consistency assessment:</b>", body_text))
    story.append(Paragraph("• LinkedIn: Professional but generic — lacks domain signature", bullet))
    story.append(Paragraph("• Media presence: Limited editorial footprint — low third-party validation", bullet))
    story.append(Paragraph("• Public speaking/panels: No visible track record — missing authority reinforcement", bullet))
    story.append(Spacer(1, 0.05*inch))
    
    story.append(Paragraph(
        "<b>Effect:</b> Each interaction requires reinterpretation. At elite visibility levels, interpretation friction = opportunity loss = slower trust velocity.",
        risk_text
    ))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("C. Third-Party Validation Infrastructure", subsection))
    story.append(Paragraph(
        "Your presence is not yet reinforced by sufficient external validation signals. In high-trust environments, perception is heavily socially validated — self-declaration alone carries limited weight.",
        body_text
    ))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(
        "Current validation gaps include:",
        body_text
    ))
    story.append(Paragraph("• No institutional affiliations visible in primary profile", bullet))
    story.append(Paragraph("• Limited media or press mentions as authority source", bullet))
    story.append(Paragraph("• Missing association markers (boards, advisory roles, selective memberships)", bullet))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(
        "<b>Consequence:</b> Verification friction in high-trust environments. People who need to quickly assess 'who you are' take longer to reach confidence — or move to someone easier to verify.",
        risk_text
    ))
    story.append(Spacer(1, 0.15*inch))
    
    # ========== PAGE 3 ==========
    story.append(Paragraph("IV. STRATEGIC EXPOSURE RISKS", section_header))
    story.append(Paragraph(
        "Based on current signal architecture, the following risks are present over the next 6-12 months:",
        body_text
    ))
    story.append(Spacer(1, 0.05*inch))
    
    story.append(Paragraph("<b>Risk 1: Reduced Conversion in High-Trust Introductions</b>", subsection))
    story.append(Paragraph(
        "When introduced to investors, board members, or strategic partners without pre-existing reputation, weak visibility infrastructure reduces conversion probability. People rely on verification signals when trust is not pre-established.",
        body_text
    ))
    story.append(Spacer(1, 0.08*inch))
    
    story.append(Paragraph("<b>Risk 2: Underestimation at First Encounter</b>", subsection))
    story.append(Paragraph(
        "Your actual capability is likely exceeding perceived weight. This creates a 'hidden tax' on every first interaction — you spend credibility capital to overcome perception gap before value demonstration begins.",
        body_text
    ))
    story.append(Spacer(1, 0.08*inch))
    
    story.append(Paragraph("<b>Risk 3: Opportunity Bypass in Competitive Contexts</b>", subsection))
    story.append(Paragraph(
        "When competing for speaking slots, board positions, media features, or investment, those with stronger perception infrastructure get prioritized. Not because they are more capable — because they are easier to justify quickly.",
        body_text
    ))
    story.append(Spacer(1, 0.08*inch))
    
    story.append(Paragraph("<b>This is not reputational damage — it is perception inefficiency.</b>", insight_text))
    story.append(Paragraph(
        "The gap between actual and perceived authority is a solvable structural problem, not a character issue.",
        body_text
    ))
    story.append(Spacer(1, 0.15*inch))
    
    # ========== PAGE 4 (if needed) ==========
    story.append(Paragraph("V. EXECUTIVE ACTION FRAMEWORK", section_header))
    
    story.append(Paragraph("Priority 1: Authority Repositioning", subsection))
    story.append(Paragraph(
        "Action: Reframe public identity to reflect decision-making capacity, domain ownership, and directional influence — not participation or contribution.",
        body_text
    ))
    story.append(Paragraph(
        "Timeline: 30 days. Impact: Immediate shift in first-impression categorization.",
        small_text
    ))
    story.append(Spacer(1, 0.08*inch))
    
    story.append(Paragraph("Priority 2: Narrative Unification", subsection))
    story.append(Paragraph(
        "Action: Every public signal should reinforce one central identity axis. Someone encountering you once should not need reinterpretation later.",
        body_text
    ))
    story.append(Paragraph(
        "Timeline: 60 days. Impact: Reduced friction in sequential interactions.",
        small_text
    ))
    story.append(Spacer(1, 0.08*inch))
    
    story.append(Paragraph("Priority 3: Third-Party Validation Infrastructure", subsection))
    story.append(Paragraph(
        "Action: Prioritise credible mentions, selective media presence, board/advisor affiliations, and high-signal association markers.",
        body_text
    ))
    story.append(Paragraph(
        "Timeline: 90-120 days. Impact: Increased verification speed in high-trust environments.",
        small_text
    ))
    story.append(Spacer(1, 0.08*inch))
    
    story.append(Paragraph("Priority 4: Visibility Footprint Expansion", subsection))
    story.append(Paragraph(
        "Action: Targeted bylined articles, podcast appearances, or panel participation in high-signal venues within your domain.",
        body_text
    ))
    story.append(Paragraph(
        "Timeline: 90 days. Impact: External validation anchors for your authority claims.",
        small_text
    ))
    story.append(Spacer(1, 0.15*inch))
    
    # FINAL DIAGNOSTIC
    story.append(Paragraph("VI. FINAL DIAGNOSTIC", section_header))
    story.append(Paragraph(
        "<b>Your current positioning is not weak — it is under-amplified relative to capability.</b>",
        insight_text
    ))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(
        "You are likely being perceived below your actual strategic value. This creates a hidden inefficiency that compounds over time — each interaction starts from a deficit that must be overcome before value is recognized.",
        body_text
    ))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(
        "Correcting this perception gap compounds into:",
        body_text
    ))
    story.append(Paragraph("• Higher trust velocity in new relationships", bullet))
    story.append(Paragraph("• Stronger inbound opportunity flow", bullet))
    story.append(Paragraph("• Improved deal positioning without changing capability", bullet))
    story.append(Paragraph("• Increased perceived authority without additional output", bullet))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph(
        "This is solvable. The gap is structural, not fundamental. With systematic execution of the framework above, perception alignment is achievable within 120 days.",
        body_text
    ))
    story.append(Spacer(1, 0.2*inch))
    
    # FOOTER
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e2e8f0')))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(f"Confidential Briefing · Prepared for {client_name} · Valid for 60 days", 
                         ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, 
                                       textColor=colors.HexColor('#8a9bb0'), alignment=1, spaceAfter=4)))
    story.append(Paragraph("VETTIFY INTELLIGENCE — Perception Advisory", 
                         ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, 
                                       textColor=colors.HexColor('#8a9bb0'), alignment=1)))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

@app.route('/download-sample-report')
def download_sample_report():
    """Download elite sample intelligence report"""
    sample_data = {
        'full_name': 'Private Client',
        'position': 'Executive',
        'email': 'client@example.com'
    }
    pdf_buffer = generate_intelligence_report(sample_data)
    return send_file(pdf_buffer, as_attachment=True, download_name="vettify_elite_briefing.pdf")
