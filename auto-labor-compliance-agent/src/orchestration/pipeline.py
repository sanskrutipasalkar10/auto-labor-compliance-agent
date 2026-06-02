import os
import glob
import re
import pandas as pd
import json
from typing import List, Optional, Dict
from langsmith import traceable 

# --- REPORTLAB IMPORTS (For Professional PDF Generation) ---
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# --- MODULE IMPORTS ---
from src.contracts.inputs import DocumentInput
from src.ingestion.pdf_parser import SanePDFParser
from src.reasoning.audit_engine import AuditEngine
from src.ingestion.web_hunter import WebHunter

class ComplianceOrchestrator:
    def __init__(self):
        print("🔧 Initializing SANE-AI Compliance Orchestrator (Monolithic Protocol)...")
        # 1. Initialize Components
        self.parser = SanePDFParser()
        # Using Gemini 2.0 Flash for its massive 1M context window (Monolithic Mode)
        self.engine = AuditEngine(model_name="gemini-2.0-flash")
        self.hunter = WebHunter()
        self.structured_dir = "auto-labor-compliance-agent/data/03_structured"

    # --- 1. NEW HELPER: TALK TO FRONTEND (WEBSOCKET BRIDGE) ---
    def _emit_update(self, message: str, percent: int, callback=None):
        """Prints to console AND sends JSON to the React Frontend via WebSocket"""
        print(f" {message}") 
        if callback:
            try:
                callback({
                    "status": "processing",
                    "message": message,
                    "progress": percent
                })
            except Exception as e:
                print(f"  ⚠️ WebSocket Emit Failed: {e}")

    def _check_existing_report(self, company_name: str) -> Optional[Dict]:
        """
        CACHE DISABLED (As requested).
        Always returns None to force fresh execution.
        """
        print(f"🔄 Fresh Audit Mode: Ignoring cache for '{company_name}'")
        return None

    def _optimize_search_query(self, company_name: str) -> str:
        """
        NUCLEAR DISAMBIGUATION (FIXED for Mahindra):
        Forces exact-match searching for conglomerates to avoid subsidiary drift.
        """
        prompt = f"""
        You are a Forensic Financial Search Expert.
        TARGET INPUT: "{company_name}"
        
        TASK: Construct a 'Nuclear' Google Search Query to find the **Parent/OEM** Annual Report/BRSR.
        
        CRITICAL RULES (Entity Isolation):
        1. **Identify the STOCK TICKER:** Use the NSE/BSE ticker (e.g., MARUTI, TATAMOTORS, M&M). This is the strongest filter.
        2. **Exact Legal Name:** Enclose the full listed name in quotes (e.g., "Maruti Suzuki India Limited").
        3. **Identify 'Poison' Keywords:** Identify Joint Ventures (JVs) or Associates that clutter search results.
           - For "Maruti" -> Poison: "Jay Bharat", "Machino", "Suzuki Motor Gujarat"
           - For "Mahindra" -> Poison: "Tech", "Finance", "Lifespace", "Holidays"
           - For "Tata" -> Poison: "TCS", "Steel", "Power", "Communications"
        4. **Domain Hint:** Prefer official investor relations domains if known.

        QUERY STRUCTURE:
        `"[Exact Legal Name]" [Ticker] "Annual Report 2024-25" -[Poison1] -[Poison2] site:bseindia.com OR site:nseindia.com OR site:official_domain filetype:pdf`
        
        OUTPUT: Return ONLY the query string.
        """
        try:
            # Generate optimized query
            optimized_query = self.engine.llm.invoke(prompt).content.strip()
            
            # --- FIX: STRICT QUOTE HANDLING ---
            # If it's Mahindra (or similar complex entity), FORCE quotes to stay.
            if "mahindra" in company_name.lower():
                if '"' not in optimized_query:
                    optimized_query = f'"{company_name}" {optimized_query}'
            else:
                # For others, we can be slightly looser, but usually keeping quotes is safer
                optimized_query = optimized_query.replace('"', '') 

            print(f"   🎯 Nuclear Query: '{optimized_query}'")
            return optimized_query
        except Exception:
            # Safe Fallback
            return f'"{company_name}" Annual Report 2024 filetype:pdf'

    def _semantic_validation(self, raw_text: str, target_company: str, filename: str) -> bool:
        """
        ANTI-PATTERN GATEKEEPER (FIXED for Mahindra):
        1. Normalizes text.
        2. Checks for Poison Entities (Context-Aware: Only checks first 1000 chars).
        3. Checks for Positive Confirmation (Alias-Aware: Accepts M&M, etc.).
        """
        # --- 1. Text Normalization ---
        # Convert to lower case and replace newlines/tabs with single spaces
        # We assume the header/identity is in the first 5000 chars
        header_text = re.sub(r'\s+', ' ', raw_text[:5000].lower())
        
        target_lower = target_company.lower()
        
        # --- 2. Poison Check (The "Do Not Entry" List) ---
        poison_map = {
            "bajaj auto": ["bajaj finance", "bajaj finserv", "bajaj holdings", "bajaj electricals", "bajaj consumer", "bajaj allianz", "housing"],
            "tata motors": ["tata steel", "tata power", "tcs", "consultancy", "chemicals", "elxsi"],
            "mahindra": ["tech mahindra", "mahindra finance", "mahindra lifespace", "club mahindra", "mahindra logistics"],
            "godrej": ["properties", "agrovet", "consumer"],
            "maruti": ["jay bharat", "machino", "jbm", "suzuki motor gujarat"]
        }
        
        for key, poisons in poison_map.items():
            if key in target_lower:
                for poison in poisons:
                    # --- FIX 2: CONTEXT AWARE POISON CHECK ---
                    # Only reject if the poison term is in the FIRST 1000 CHARS (Cover Page/Header)
                    # This allows a valid report to mention subsidiaries later on without being rejected.
                    check_zone = header_text[:1000] if "mahindra" in target_lower else header_text
                    
                    if poison in check_zone:
                        print(f"   ⛔ GATEKEEPER REJECTED: {filename}")
                        print(f"      Reason: Found Poison Entity '{poison}' in document header/title.")
                        return False # REJECT
        
        # --- 3. Positive Confirmation (The "Must Be Present" Check) ---
        valid_aliases = [target_lower.replace("limited", "").replace("ltd", "").strip()]

        # --- FIX 3: ADD ALIASES FOR MAHINDRA ---
        if "mahindra" in target_lower:
            valid_aliases.extend(["m&m", "mahindra & mahindra", "mahindra and mahindra"])
            
        # Check if ANY valid alias is present
        is_confirmed = any(alias in header_text for alias in valid_aliases)

        if not is_confirmed:
            print(f"   ⛔ GATEKEEPER REJECTED: {filename}")
            print(f"      Reason: Target Name (or valid alias) NOT found in document header.")
            return False # REJECT

        return True

    @traceable(name="Full Audit Pipeline", run_type="chain")
    def run_pipeline(self, specific_files: Optional[List[str]] = None, target_company: str = "Consolidated Entity", progress_callback=None):
        
        # --- STAGE 1: INITIALIZATION (0-5%) ---
        self._emit_update(f"🚀 Initializing SANE-AI Protocol for {target_company}...", 5, progress_callback)
        
        financial_truth = None 
        full_consolidated_text = ""
        
        # --- STAGE 2: HUNTING (5-50%) ---
        # If files are NOT provided, we hunt for them with retry logic
        if not specific_files:
            valid_files = []
            attempt = 0
            current_exclusions = [] # Start with no specific exclusions
            
            # Retry Loop (Max 3 attempts to correct course)
            while attempt < 3:
                if attempt > 0:
                    self._emit_update(f"🔄 Retrying search with Exclusion Filter: {current_exclusions}", 10 + (attempt * 5), progress_callback)

                # Dynamic progress calculation based on attempt
                base_progress = 10 + (attempt * 10)
                self._emit_update(f"🌍 Hunting for documents (Attempt {attempt+1})...", base_progress, progress_callback)
                
                # 1. Hunt with current exclusions
                candidates = self.hunter.hunt_for_company(target_company, exclusions=current_exclusions)
                
                if not candidates:
                    self._emit_update("⚠️ No files found via Deep Search.", base_progress + 5, progress_callback)
                    break

                # 2. Validate Each Candidate
                files_passed_validation = []
                rejection_occured = False
                
                total_candidates = len(candidates)
                for idx, file_path in enumerate(candidates):
                    filename = os.path.basename(file_path)
                    
                    # Calculate granular progress for each file
                    step_progress = base_progress + int((idx / total_candidates) * 20)
                    self._emit_update(f"🔎 Inspecting: {filename}...", step_progress, progress_callback)
                    
                    # Auto-tag document type
                    doc_type = "Supporting Document"
                    if "BRSR" in filename: doc_type = "BRSR / Sustainability Report"
                    elif "Annual" in filename: doc_type = "Annual Financial Report"
                    elif "Investor" in filename: doc_type = "Investor Presentation"
                    elif "EHS" in filename: doc_type = "EHS Report"
                    elif "Financial" in filename: doc_type = "Quarterly Results" 
                    
                    try:
                        doc_input = DocumentInput(filename=filename, file_path=file_path, doc_type=doc_type)
                        parse_result = self.parser.parse_document(doc_input) # Parses text
                        raw_text = parse_result["content"]
                        
                        # GATEKEEPER CHECK
                        if self._semantic_validation(raw_text, target_company, filename):
                            self._emit_update(f"✅ Verified & Locked: {filename}", step_progress + 2, progress_callback)
                            files_passed_validation.append(file_path)
                            # Accumulate text for the final report immediately
                            # CRITICAL: We add headers so the AuditEngine's "Searcher" can find sections easily
                            full_consolidated_text += f"\n\n=== SOURCE DOCUMENT: {doc_type} ({filename}) ===\n{raw_text}\n===========================================\n"
                        else:
                            # 3. LEARN from the mistake
                            # We normalize text to find the culprit keyword
                            clean_text = re.sub(r'\s+', ' ', raw_text[:5000].lower())
                            
                            if "finance" in clean_text: current_exclusions.append("finance")
                            if "holdings" in clean_text: current_exclusions.append("holdings")
                            if "consumer" in clean_text: current_exclusions.append("consumer")
                            if "electrical" in clean_text: current_exclusions.append("electrical")
                            if "finserv" in clean_text: current_exclusions.append("finserv")
                            if "housing" in clean_text: current_exclusions.append("housing")
                            if "logistics" in clean_text: current_exclusions.append("logistics") # Added logistics for Mahindra
                                
                            self._emit_update(f"⛔ Rejected: {filename} (Invalid Content)", step_progress + 2, progress_callback)
                            try:
                                os.remove(file_path) # Delete the wrong file so it doesn't clutter
                            except:
                                pass
                            rejection_occured = True
                            
                    except Exception as e:
                        print(f" ❌ Error validating {filename}: {e}")

                if files_passed_validation and not rejection_occured:
                    self._emit_update(f"📚 Compliance Data Locked: {len(files_passed_validation)} Documents.", 50, progress_callback)
                    specific_files = files_passed_validation
                    break # Success! All files are good.
                
                elif files_passed_validation and rejection_occured:
                      print(f"   ⚠️ Some files were rejected. Keeping the valid ones and proceeding.")
                      specific_files = files_passed_validation
                      # We break here because we have at least SOME valid files
                      break

                # If ALL files were rejected, retry with new exclusions.
                if rejection_occured and not files_passed_validation:
                    # Remove duplicates from exclusions
                    current_exclusions = list(set(current_exclusions))
                    attempt += 1
                else:
                    break

            if not specific_files:
                self._emit_update("❌ Failed to find valid documents. Aborting.", 0, progress_callback)
                return

        else:
            # If files WERE provided (manual mode), just process them
            print(f"\n📚 Processing {len(specific_files)} provided documents for {target_company}...")
            for file_path in specific_files:
                filename = os.path.basename(file_path)
                doc_type = "Supporting Document" # Simplified for manual mode
                try:
                    doc_input = DocumentInput(filename=filename, file_path=file_path, doc_type=doc_type)
                    parse_result = self.parser.parse_document(doc_input)
                    raw_text = parse_result["content"]
                    full_consolidated_text += f"\n\n=== SOURCE DOCUMENT: {doc_type} ({filename}) ===\n{raw_text}\n===========================================\n"
                except:
                    pass

        if len(full_consolidated_text) < 100:
            self._emit_update("❌ Audit Aborted: Insufficient Data.", 0, progress_callback)
            return

        # --- STAGE 3: AI ANALYSIS (50-90%) ---
        self._emit_update(f"🧠 AI Auditor: Analyzing {len(full_consolidated_text)} chars...", 60, progress_callback)
        
        # ATTEMPT FINANCIAL TRUTH ACQUISITION BEFORE AUDIT
        self._emit_update("💰 Fetching Real-time Financial Truth...", 70, progress_callback)
        try:
             financial_truth = self.hunter.get_financial_truth(target_company)
        except Exception:
             print("   ⚠️ Could not fetch API financials.")

        # PASS EVERYTHING TO THE ENGINE
        self._emit_update("🔍 Running Forensic Cross-Validation...", 80, progress_callback)
        audit_report = self.engine.analyze_document(full_consolidated_text, target_company, financial_truth)

        # 2. LOGIC: Check if Financials are Missing/N/A
        fin = audit_report.api_financials
        missing_indicators = ["N/A", "Not Disclosed", "0", None, "", "USD 0", "INR 0"]
        
        is_revenue_missing = str(fin.revenue).strip() in missing_indicators
        is_profit_missing = str(fin.net_income).strip() in missing_indicators

        if is_revenue_missing or is_profit_missing:
            print(f"   ⚠️ Financials missing in PDF extraction. Triggering API Fallback...")
            if financial_truth:
                print(f"   🔄 Patching Report with API Data: {financial_truth}")
                if is_revenue_missing:
                    audit_report.api_financials.revenue = str(financial_truth.get('API_Revenue', 'N/A')) + " (Source: API)"
                if is_profit_missing:
                    audit_report.api_financials.net_income = str(financial_truth.get('API_NetIncome', 'N/A')) + " (Source: API)"
                if str(fin.ebitda).strip() in missing_indicators:
                    audit_report.api_financials.ebitda = str(financial_truth.get('API_EBITDA', 'N/A')) + " (Source: API)"
                if str(fin.employee_cost).strip() in missing_indicators:
                    audit_report.api_financials.employee_cost = str(financial_truth.get('API_Employee_Cost', 'N/A')) + " (Source: API)"
                print("   ✅ Financials successfully patched via External API.")
            else:
                print("   ⚠️ API returned no data. Financials remain N/A.")
        
        # --- STAGE 4: GENERATION (90-100%) ---
        self._emit_update("📊 Generating Strategic PDF Report...", 90, progress_callback)
        safe_name = target_company.replace(" ", "_")
        self._save_json(audit_report, f"{safe_name}_Consolidated_Report.json")
        self._generate_reportlab_pdf(audit_report, f"{safe_name}_Consolidated_Report.pdf")
        self._update_master_csv([self._flatten_report(audit_report)])
        
        self._emit_update("✅ Audit Complete. Report Ready.", 100, progress_callback)
        return audit_report

    def _save_json(self, report, filename):
        os.makedirs(self.structured_dir, exist_ok=True)
        path = os.path.join(self.structured_dir, filename)
        
        # 1. Get the standard nested data
        data = report.model_dump() if hasattr(report, 'model_dump') else report
        
        # 2. Get the flat data (Business Intel, Labour Code)
        flat_data = self._flatten_report(report)
        
        # 3. Merge
        merged_data = {**data, **flat_data}
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(merged_data, f, indent=2, ensure_ascii=False)

    # --- THE REPORTLAB ENGINE (PROFESSIONAL PDF GENERATION) ---
    def _generate_reportlab_pdf(self, r, filename):
        """
        Generates a professional corporate PDF using ReportLab elements.
        Includes Forensic Business Intelligence and Labour Code Provisions.
        """
        pdf_path = os.path.join(self.structured_dir, filename)
        doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        
        # Styles Setup
        styles = getSampleStyleSheet()
        
        # Custom Corporate Styles
        title_style = ParagraphStyle(
            'MainTitle', 
            parent=styles['Heading1'], 
            fontSize=24, 
            textColor=colors.HexColor('#0f172a'), 
            spaceAfter=20
        )
        h2_style = ParagraphStyle(
            'SectionHeader', 
            parent=styles['Heading2'], 
            fontSize=14, 
            textColor=colors.HexColor('#1e40af'), 
            borderPadding=5, 
            borderColor=colors.HexColor('#e2e8f0'), 
            borderWidth=0, 
            spaceBefore=15, 
            spaceAfter=10
        )
        normal_style = ParagraphStyle(
            'BodyText', 
            parent=styles['Normal'], 
            fontSize=10, 
            leading=14, 
            spaceAfter=6
        )
        
        elements = []

        # Handle Object vs Dict access
        c_name = r.company_name if hasattr(r, 'company_name') else r.get('company_name', 'N/A')
        c_period = r.report_period if hasattr(r, 'report_period') else r.get('report_period', 'N/A')
        risk_score = r.overall_risk_score if hasattr(r, 'overall_risk_score') else r.get('overall_risk_score', 'N/A')

        # --- 1. Header Section ---
        elements.append(Paragraph(f"Compliance Audit: {c_name}", title_style))
        elements.append(Paragraph(f"<b>Period:</b> {c_period}", normal_style))
        elements.append(Spacer(1, 10))

        # Risk Badge Logic
        risk_text = risk_score.upper()
        if "LOW" in risk_text:
            risk_color = colors.green
        elif "MODERATE" in risk_text or "MEDIUM" in risk_text:
            risk_color = colors.orange
        else:
            risk_color = colors.red
            
        risk_table = Table([[f"OVERALL RISK: {risk_text}"]], colWidths=[6*cm])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), risk_color), 
            ('TEXTCOLOR', (0,0), (-1,-1), colors.white), 
            ('ALIGN', (0,0), (-1,-1), 'CENTER'), 
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(risk_table)
        elements.append(Spacer(1, 20))

        # --- 2. FORENSIC BUSINESS INTELLIGENCE (NEW) ---
        elements.append(Paragraph("1. Forensic Business Intelligence", h2_style))
        
        # Safe Attribute Access Helper
        def get_val(obj, key, default):
            if isinstance(obj, dict): return obj.get(key, default)
            return getattr(obj, key, default)

        # A. Labour Code Impact Box
        prov = get_val(r, 'labour_code_impact', {})
        # SAFEGUARD: Check if 'prov' exists before accessing attributes
        if prov:
            fiscal_period = get_val(prov, 'fiscal_period', 'Q3 FY26') # Default if missing
            amount = get_val(prov, 'provision_amount', 'N/A')
            desc = get_val(prov, 'impact_description', 'No details available')
            
            prov_text = f"<b>LABOUR CODE FINANCIAL IMPACT ({fiscal_period}):</b><br/>"
            
            if amount != "N/A" and amount is not None:
                prov_text += f"<font size=14 color=red><b>{amount}</b></font><br/>{desc}"
            else:
                prov_text += "<i>No specific provision note found in Q3 results.</i>"
        else:
            # Fallback if the entire object is None
            prov_text = "<b>LABOUR CODE FINANCIAL IMPACT:</b><br/><i>No data extracted.</i>"
        
        prov_table = Table([[Paragraph(prov_text, normal_style)]], colWidths=[17*cm])
        prov_table.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 1, colors.red), 
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fff1f1')), 
            ('PADDING', (0,0), (-1,-1), 10)
        ]))
        elements.append(prov_table)
        elements.append(Spacer(1, 10))

        # B. Products & Customers Grid
        intel = get_val(r, 'business_intel', {})
        # Data preparation with safe fallbacks
        if intel:
            key_products_list = get_val(intel, 'key_products', [])
            major_customers_list = get_val(intel, 'major_customers', [])
            
            key_products = ", ".join(key_products_list) if key_products_list else "Not extracted"
            major_customers = ", ".join(major_customers_list) if major_customers_list else "Not extracted"
        else:
            key_products = "Not extracted"
            major_customers = "Not extracted"

        intel_data = [
            [Paragraph("<b>KEY PRODUCTS</b>", normal_style), Paragraph("<b>MAJOR CUSTOMERS</b>", normal_style)],
            [Paragraph(key_products, normal_style), Paragraph(major_customers, normal_style)]
        ]
        
        intel_table = Table(intel_data, colWidths=[8.5*cm, 8.5*cm])
        intel_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey), 
            ('VALIGN', (0,0), (-1,-1), 'TOP'), 
            ('PADDING', (0,0), (-1,-1), 8),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')) # Header row background
        ]))
        elements.append(intel_table)
        elements.append(Spacer(1, 15))

        # --- 3. Executive Summary Box ---
        elements.append(Paragraph("2. Executive Summary", h2_style))
        
        exec_sum = get_val(r, 'executive_summary', {})
        overview = get_val(exec_sum, 'overview', 'N/A')
        key_finding = get_val(exec_sum, 'key_finding', 'N/A')

        summary_content = f"<b>Overview:</b> {overview}<br/><br/><b>💡 Key Insight:</b> {key_finding}"
        summary_table = Table([[Paragraph(summary_content, normal_style)]], colWidths=[17*cm])
        summary_table.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
            ('PADDING', (0,0), (-1,-1), 12),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 15))

        # --- 4. Supply Chain & Vendor Intelligence ---
        elements.append(Paragraph("3. Supply Chain & Vendor Intelligence", h2_style))
        
        # Vendor List Table
        vendors = get_val(r, 'vendors', [])
        if vendors and len(vendors) > 0:
            elements.append(Paragraph("<b>Key Vendors Identified (Related Parties):</b>", normal_style))
            
            # Format vendor list as a table for better readability
            vendor_data = []
            for i, v in enumerate(vendors[:15]): # Limit to top 15 to fit page
                vendor_data.append([f"{i+1}.", v])
            
            vendor_table = Table(vendor_data, colWidths=[1*cm, 16*cm])
            vendor_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('PADDING', (0,0), (-1,-1), 2),
                ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#334155')),
            ]))
            elements.append(vendor_table)
        else:
            elements.append(Paragraph("<i>No specific vendor names extracted from available documents.</i>", normal_style))
        
        elements.append(Spacer(1, 10))

        # Liability Box
        supply_chain = get_val(r, 'supply_chain_compliance', {})
        liability_val = get_val(supply_chain, 'principal_employer_liability', 'N/A')

        liability_text = f"<b>Principal Employer Liability Analysis:</b> {liability_val}"
        liability_table = Table([[Paragraph(liability_text, normal_style)]], colWidths=[17*cm])
        liability_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fff1f2')), # Light Red
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#fda4af')),
            ('PADDING', (0,0), (-1,-1), 8),
        ]))
        elements.append(liability_table)
        elements.append(Spacer(1, 15))

        # --- 5. Financial Grid ---
        elements.append(Paragraph("4. Financial Intelligence", h2_style))
        
        api_fin = get_val(r, 'api_financials', {})
        
        # Header Row
        fin_data = [['Revenue', 'EBITDA', 'Net Income', 'Emp. Cost']]
        # Data Row
        fin_data.append([
            get_val(api_fin, 'revenue', 'N/A'), 
            get_val(api_fin, 'ebitda', 'N/A'), 
            get_val(api_fin, 'net_income', 'N/A'), 
            get_val(api_fin, 'employee_cost', 'N/A')
        ])
        
        fin_table = Table(fin_data, colWidths=[4.25*cm]*4)
        fin_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')), # Header Blue
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('PADDING', (0,0), (-1,-1), 8),
            ('BACKGROUND', (0,1), (-1,-1), colors.white), # Data White
            ('TEXTCOLOR', (0,1), (-1,-1), colors.black),
        ]))
        elements.append(fin_table)
        elements.append(Spacer(1, 15))

        # --- 6. Labour Code Analysis (Reusable Table Builder) ---
        def build_compliance_section(title, data_obj):
            elements.append(Paragraph(title, h2_style))
            
            # Table Header
            table_data = [['Area', 'Status', 'Evidence Snippet']]
            
            # Helper to process Pydantic models
            data_dict = data_obj.model_dump() if hasattr(data_obj, 'model_dump') else data_obj
            
            if not data_dict: return

            for key, val in data_dict.items():
                if isinstance(val, dict) and 'status' in val:
                    # Clean up Key Name
                    clean_key = key.replace('_', ' ').replace('status', '').strip().title()
                    
                    # Status Color Logic (Text Color)
                    status_text = val['status'].upper()
                    status_para_style = ParagraphStyle('StatusStyle', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold')
                    
                    if "COMPLIANT" in status_text:
                        status_para = Paragraph(f"<font color='green'>{status_text}</font>", status_para_style)
                    elif "RISK" in status_text or "NON" in status_text:
                        status_para = Paragraph(f"<font color='red'>{status_text}</font>", status_para_style)
                    else:
                        status_para = Paragraph(f"<font color='orange'>{status_text}</font>", status_para_style)

                    # Evidence Text
                    evidence_text = val.get('evidence_snippet', 'N/A')
                    if len(evidence_text) > 300: evidence_text = evidence_text[:300] + "..."
                    evidence_para = Paragraph(evidence_text, normal_style)
                    
                    table_data.append([clean_key, status_para, evidence_para])

            if len(table_data) > 1:
                t = Table(table_data, colWidths=[4*cm, 3.5*cm, 9.5*cm])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e2e8f0')), # Header Grey
                    ('TEXTCOLOR', (0,0), (-1,0), colors.black),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
                    ('BOX', (0,0), (-1,-1), 0.5, colors.grey),
                    ('PADDING', (0,0), (-1,-1), 6),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 10))

        # Add Sections
        labor_code = get_val(r, 'labor_code_analysis', {})
        if labor_code:
            build_compliance_section("5A. Wages & Remuneration", get_val(labor_code, 'wages', {}))
            build_compliance_section("5B. OSH & Safety", get_val(labor_code, 'osh', {}))
            build_compliance_section("5C. Industrial Relations", get_val(labor_code, 'ir', {}))
            build_compliance_section("5D. Social Security", get_val(labor_code, 'social_security', {}))

        elements.append(PageBreak()) # New Page

        # --- 7. Workforce Profile ---
        elements.append(Paragraph("6. Workforce Profile", h2_style))
        workforce_profile = get_val(r, 'workforce_profile', [])
        
        if workforce_profile:
            wf_data = [['Category', 'Total', 'Male', 'Female', 'Turnover']]
            for w in workforce_profile:
                wf_data.append([
                    Paragraph(get_val(w, 'category', 'N/A'), normal_style), 
                    get_val(w, 'total_count', 'N/A'), 
                    get_val(w, 'male_count', 'N/A'), 
                    get_val(w, 'female_count', 'N/A'), 
                    get_val(w, 'turnover_rate', 'N/A')
                ])
            
            wf_table = Table(wf_data, colWidths=[6*cm, 2.5*cm, 2.5*cm, 2.5*cm, 3.5*cm])
            wf_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e40af')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('ALIGN', (1,0), (-1,-1), 'RIGHT'), # Numbers aligned right
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('PADDING', (0,0), (-1,-1), 6),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.white]),
            ]))
            elements.append(wf_table)
        else:
            elements.append(Paragraph("No detailed workforce data extracted.", normal_style))
        
        elements.append(Spacer(1, 15))

        # --- 8. Strategic Recommendations ---
        elements.append(Paragraph("7. Strategic Recommendations", h2_style))
        
        strat_plan = get_val(r, 'strategic_plan', {})
        recommendations = get_val(strat_plan, 'recommendations', [])

        if recommendations:
            rec_data = []
            for i, rec in enumerate(recommendations, 1):
                rec_data.append([f"{i}.", Paragraph(rec, normal_style)])
            
            rec_table = Table(rec_data, colWidths=[1*cm, 16*cm])
            rec_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('PADDING', (0,0), (-1,-1), 4),
            ]))
            elements.append(rec_table)

        # Footer
        elements.append(Spacer(1, 30))
        elements.append(Paragraph("Generated by SANE-AI AutoLabor Agent • Forensic Audit Protocol", 
            ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_CENTER)))

        # Build PDF
        try:
            doc.build(elements)
            print(f"   ✅ ReportLab PDF Generated: {pdf_path}")
        except Exception as e:
            print(f"   ❌ ReportLab Generation Failed: {e}")

    def _flatten_report(self, report):
        if isinstance(report, dict): return report
        r = report.model_dump()
        
        # --- ROBUST SAFEGUARD: EXTRACT NESTED DATA SAFELY ---
        
        # 1. Safely extract Labour Code Provision
        labour_impact = r.get("labour_code_impact") or {} # Defaults to empty dict if None
        provision_amount = labour_impact.get("provision_amount", "N/A")
        impact_description = labour_impact.get("impact_description", "N/A")

        # 2. Safely extract Business Intelligence
        biz_intel = r.get("business_intel") or {}
        key_products = ", ".join(biz_intel.get("key_products", [])) if biz_intel.get("key_products") else "N/A"
        major_customers = ", ".join(biz_intel.get("major_customers", [])) if biz_intel.get("major_customers") else "N/A"

        # 3. Safely extract Vendors
        vendors = r.get("vendors") or []
        top_vendors = ", ".join(vendors[:5]) if vendors else "N/A"

        # 4. Safely extract Wages
        wages = r["labor_code_analysis"]["wages"]
        wage_status = wages["minimum_wage_status"]["status"]

        # 5. Safely extract Workforce
        wf_turnover = r["workforce_profile"][0]["turnover_rate"] if r.get("workforce_profile") else "N/A"

        return {
            "Company": r["company_name"],
            "Period": r["report_period"],
            "Risk Score": r["overall_risk_score"],
            
            # --- MAPS DIRECTLY TO FRONTEND KEYS ---
            "Labour_Provision": provision_amount,
            "Labour_Provision_Desc": impact_description,
            "Top_Products": key_products,
            "Major_Customers": major_customers,
            "Top_Vendors": top_vendors,
            "Wage_Status": wage_status,
            "Workforce_Turnover": wf_turnover,
            
            # --- Standard Compliance Fields ---
            "Health_Status": r["labor_code_analysis"]["osh"]["safety_systems_status"]["status"],
            "Strike_Risk": r["labor_code_analysis"]["ir"]["disputes_strikes_status"]["status"],
            "Strategic_Action": r["strategic_plan"]["recommendations"][0] if r["strategic_plan"]["recommendations"] else "N/A"
        }

    def _update_master_csv(self, new_results: List[Dict]):
        if not new_results: return
        csv_path = os.path.join(self.structured_dir, "Master_Compliance_Tracker.csv")
        new_df = pd.DataFrame(new_results)
        
        if os.path.exists(csv_path):
            existing_df = pd.read_csv(csv_path)
            combined = pd.concat([existing_df, new_df]).drop_duplicates(subset=["Company", "Period"], keep='last')
            combined.to_csv(csv_path, index=False)
        else:
            new_df.to_csv(csv_path, index=False)
        print(f"   📊 Master CSV Updated.")