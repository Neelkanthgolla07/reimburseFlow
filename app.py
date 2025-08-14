import os
import json
import base64
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
import google.generativeai as genai
from PIL import Image
import io
import config

app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configure Gemini AI
genai.configure(api_key=config.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class ReimbursementProcessor:
    def __init__(self):
        self.data_file = 'claims_data.json'
        self.processed_claims = self.load_claims()
    
    def load_claims(self):
        """Load claims from JSON file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading claims data: {e}")
            return []
    
    def save_claims(self):
        """Save claims to JSON file"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.processed_claims, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving claims data: {e}")
    
    def extract_bill_details(self, image_data):
        """Extract bill details using Gemini Vision API"""
        try:
            # Convert image data to PIL Image
            image = Image.open(io.BytesIO(image_data))
            
            # Prepare prompt for OCR extraction
            prompt = """
            Analyze this bill/receipt image and extract the following information in JSON format:
            {
                "bill_number": "extracted bill/invoice number",
                "bill_date": "YYYY-MM-DD format",
                "vendor_name": "merchant/vendor name",
                "transaction_category": "category like Travel, Food, Office Supplies, etc.",
                "purpose": "inferred purpose from bill type",
                "amount": numeric_amount_only,
                "currency": "INR or other currency",
                "product": "product/service category",
                "cluster_location": "location if mentioned",
                "confidence_score": confidence_percentage_as_number
            }
            
            Rules:
            - Extract exact text as visible
            - Use YYYY-MM-DD for dates
            - Amount should be numeric only (no currency symbols)
            - If information is unclear, use null
            - Provide confidence score (0-100) for overall extraction
            """
            
            response = model.generate_content([prompt, image])
            extracted_text = response.text.strip()
            
            # Clean and parse JSON response
            if extracted_text.startswith('```json'):
                extracted_text = extracted_text[7:-3]
            elif extracted_text.startswith('```'):
                extracted_text = extracted_text[3:-3]
            
            try:
                bill_data = json.loads(extracted_text)
                return bill_data
            except json.JSONDecodeError:
                # Fallback parsing if JSON is malformed
                return {
                    "bill_number": None,
                    "bill_date": None,
                    "vendor_name": None,
                    "transaction_category": "Other",
                    "purpose": "Bill processing",
                    "amount": 0,
                    "currency": "INR",
                    "product": "General",
                    "cluster_location": None,
                    "confidence_score": 50
                }
                
        except Exception as e:
            print(f"OCR Error: {str(e)}")
            return {
                "bill_number": None,
                "bill_date": None,
                "vendor_name": None,
                "transaction_category": "Other",
                "purpose": "Bill processing",
                "amount": 0,
                "currency": "INR",
                "product": "General",
                "cluster_location": None,
                "confidence_score": 0
            }
    
    def validate_and_process_claim(self, form_data, bill_images):
        """Process complete reimbursement claim"""
        
        # Extract employee details
        employee_details = {
            "form_filled_by": form_data.get('employee_name', ''),
            "department": form_data.get('department', ''),
            "hod": form_data.get('hod', ''),
            "hod_email": form_data.get('hod_email', ''),
            "cc_emails": form_data.get('cc_emails', '').split(',') if form_data.get('cc_emails') else [],
            "additional_cc": form_data.get('additional_cc', '').split(',') if form_data.get('additional_cc') else [],
            "mode_of_payment": form_data.get('payment_mode', 'Bank Transfer')
        }
        
        # Extract claim details
        claim_details = {
            "transaction_category": form_data.get('transaction_category', ''),
            "purpose": form_data.get('purpose', ''),
            "product": form_data.get('product', ''),
            "cluster": form_data.get('cluster', ''),
            "remarks": form_data.get('remarks', ''),
            "people_involved": form_data.get('people_involved', '').split(',') if form_data.get('people_involved') else []
        }
        
        # Process bills
        processed_bills = []
        
        if form_data.get('bill_type') == 'no_bill':
            # Handle "No Bill" case
            bill_data = {
                "bill_number": "NO-BILL",
                "bill_date": datetime.now().strftime('%Y-%m-%d'),
                "vendor_name": "N/A",
                "transaction_category": claim_details["transaction_category"],
                "purpose": claim_details["purpose"],
                "amount": float(form_data.get('manual_amount', 0)),
                "currency": "INR",
                "product": claim_details["product"],
                "cluster_location": claim_details["cluster"],
                "needs_review": True,
                "change_flag": False,
                "duplicate_detected": False,
                "approval_status": "needs_review",
                "rejection_reason": None,
                "bill_type": "no_bill",
                "comments": form_data.get('comments', '')
            }
            processed_bills.append(bill_data)
        else:
            # Process uploaded bill images
            for image_data in bill_images:
                extracted_data = self.extract_bill_details(image_data)
                
                # Check confidence and set flags
                needs_review = extracted_data.get('confidence_score', 100) < 85
                
                # Check for changes from manual entry
                change_flag = False
                manual_amount = form_data.get('manual_amount')
                manual_bill_number = form_data.get('manual_bill_number')
                
                if manual_amount and abs(float(manual_amount) - float(extracted_data.get('amount', 0))) > 0.01:
                    change_flag = True
                if manual_bill_number and manual_bill_number != extracted_data.get('bill_number'):
                    change_flag = True
                
                # Check for duplicates (simplified check)
                duplicate_detected = self.check_duplicate(
                    extracted_data.get('bill_number'),
                    extracted_data.get('vendor_name'),
                    extracted_data.get('amount')
                )
                
                bill_data = {
                    "bill_number": extracted_data.get('bill_number', ''),
                    "bill_date": extracted_data.get('bill_date', datetime.now().strftime('%Y-%m-%d')),
                    "vendor_name": extracted_data.get('vendor_name', ''),
                    "transaction_category": extracted_data.get('transaction_category', claim_details["transaction_category"]),
                    "purpose": extracted_data.get('purpose', claim_details["purpose"]),
                    "amount": float(extracted_data.get('amount', 0)),
                    "currency": extracted_data.get('currency', 'INR'),
                    "product": extracted_data.get('product', claim_details["product"]),
                    "cluster_location": extracted_data.get('cluster_location', claim_details["cluster"]),
                    "needs_review": needs_review,
                    "change_flag": change_flag,
                    "duplicate_detected": duplicate_detected,
                    "approval_status": "needs_review" if needs_review or change_flag or duplicate_detected else "pending",
                    "rejection_reason": None
                }
                processed_bills.append(bill_data)
        
        # Determine overall status
        overall_status = "pending"
        if all(bill["approval_status"] == "approved" for bill in processed_bills):
            overall_status = "approved"
        elif any(bill["approval_status"] == "approved" for bill in processed_bills):
            overall_status = "partially_approved"
        elif all(bill["approval_status"] == "rejected" for bill in processed_bills):
            overall_status = "rejected"
        
        result = {
            "id": f"CLM_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.processed_claims)+1:03d}",
            "employee_details": employee_details,
            "claim_details": claim_details,
            "bills": processed_bills,
            "overall_status": overall_status,
            "timestamp": datetime.now().isoformat()
        }
        
        # Store for duplicate checking
        self.processed_claims.append(result)
        
        # Save to JSON file
        self.save_claims()
        
        return result
    
    def check_duplicate(self, bill_number, vendor_name, amount):
        """Check for potential duplicates"""
        if not bill_number or not vendor_name or not amount:
            return False
        
        for claim in self.processed_claims:
            for bill in claim["bills"]:
                if (bill.get("bill_number") == bill_number and 
                    bill.get("vendor_name") == vendor_name and 
                    abs(bill.get("amount", 0) - float(amount)) < 0.01):
                    return True
        return False
    
    def get_all_claims(self):
        """Get all claims with fresh data from file"""
        self.processed_claims = self.load_claims()
        return self.processed_claims
    
    def get_claim_by_id(self, claim_id):
        """Get specific claim by ID"""
        claims = self.get_all_claims()
        for claim in claims:
            if claim.get('id') == claim_id:
                return claim
        return None
    
    def delete_claim(self, claim_id):
        """Delete a claim by ID"""
        self.processed_claims = self.load_claims()
        self.processed_claims = [claim for claim in self.processed_claims if claim.get('id') != claim_id]
        self.save_claims()
        return True

# Initialize processor
processor = ReimbursementProcessor()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit-claim', methods=['POST'])
def submit_claim():
    try:
        # Get form data
        form_data = request.form.to_dict()
        
        # Handle file uploads
        bill_images = []
        if 'bill_images' in request.files:
            files = request.files.getlist('bill_images')
            for file in files:
                if file and file.filename and allowed_file(file.filename):
                    # Read image data
                    image_data = file.read()
                    bill_images.append(image_data)
        
        # Process the claim
        result = processor.validate_and_process_claim(form_data, bill_images)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

@app.route('/claims')
def view_claims():
    claims = processor.get_all_claims()
    return render_template('claims.html', claims=claims)

@app.route('/api/claims')
def api_claims():
    claims = processor.get_all_claims()
    return jsonify(claims)

@app.route('/api/claims/<claim_id>')
def api_claim_detail(claim_id):
    claim = processor.get_claim_by_id(claim_id)
    if claim:
        return jsonify(claim)
    return jsonify({"error": "Claim not found"}), 404

@app.route('/api/claims/<claim_id>', methods=['DELETE'])
def api_delete_claim(claim_id):
    if processor.delete_claim(claim_id):
        return jsonify({"success": True, "message": "Claim deleted successfully"})
    return jsonify({"error": "Claim not found"}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)