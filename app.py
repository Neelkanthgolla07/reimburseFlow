import os
import json
import base64
import csv
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
import google.generativeai as genai
from PIL import Image
import io
import config
import firebase_admin
from firebase_admin import credentials, auth
from functools import wraps

app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize Firebase Admin SDK
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
    print("Firebase Admin SDK initialized successfully")
except Exception as e:
    print(f"Warning: Firebase Admin SDK initialization failed: {e}")
    print("Firebase authentication features will not be available")

# Configure Gemini AI
genai.configure(api_key=config.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# Load Employee Data
EMPLOYEE_DATA_PATH = os.path.join(os.path.dirname(__file__), "employee_data.csv")

def load_employee_data():
    """Load employee data from CSV file"""
    employee_dict = {}
    try:
        with open(EMPLOYEE_DATA_PATH, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                email = row.get("Employee Email ID", "").strip().lower()
                if email:
                    employee_dict[email] = row
        print(f"Loaded {len(employee_dict)} employee records")
        return employee_dict
    except Exception as e:
        print(f"Error loading employee data: {e}")
        return {}

EMPLOYEE_DATA = load_employee_data()

# Allow common image formats that work reliably with Gemini
ALLOWED_EXTENSIONS = {
    # Images (work reliably)
    'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff',
    # Documents (basic support)
    'pdf', 'txt',
    # Note: PDF requires poppler-utils to be installed
}

def allowed_file(filename):
    """Check if the file is allowed - now accepts most common formats that Gemini can process"""
    if not filename or '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def verify_firebase_token(id_token):
    """Verify Firebase ID token and return user info"""
    try:
        print(f"Attempting to verify token: {id_token[:20]}...")
        decoded_token = auth.verify_id_token(id_token)
        print(f"Token verified successfully for user: {decoded_token.get('email')}")
        return decoded_token
    except Exception as e:
        print(f"Token verification failed: {e}")
        print(f"Error type: {type(e).__name__}")
        return None

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
    
    def extract_bill_details(self, file_data, filename=None):
        """Extract bill details using Gemini Vision API - supports any file format"""
        try:
            import io  # Import io module at the beginning
            
            # For PDF files, we need to handle them differently
            if filename and filename.lower().endswith('.pdf'):
                print(f"Processing PDF file: {filename}")
                
                # Try multiple approaches for PDF processing
                image = None
                
                # Method 1: Try pdf2image first
                try:
                    from pdf2image import convert_from_bytes
                    print("Attempting PDF conversion with pdf2image...")
                    images = convert_from_bytes(file_data, first_page=1, last_page=1, dpi=200)
                    if images:
                        image = images[0]
                        print("PDF successfully converted to image using pdf2image")
                except ImportError:
                    print("pdf2image not available, trying PyMuPDF...")
                except Exception as e:
                    print(f"pdf2image failed: {e}, trying PyMuPDF...")
                
                # Method 2: Try PyMuPDF as fallback
                if image is None:
                    try:
                        import fitz  # PyMuPDF
                        print("Attempting PDF conversion with PyMuPDF...")
                        pdf_document = fitz.open(stream=file_data, filetype="pdf")
                        page = pdf_document[0]  # Get first page
                        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))  # High resolution
                        img_data = pix.tobytes("png")
                        image = Image.open(io.BytesIO(img_data))
                        pdf_document.close()
                        print("PDF successfully converted to image using PyMuPDF")
                    except ImportError:
                        print("PyMuPDF not available")
                    except Exception as e:
                        print(f"PyMuPDF failed: {e}")
                
                # Method 3: Try direct PDF processing with Gemini (if supported)
                if image is None:
                    try:
                        print("Attempting direct PDF processing with Gemini...")
                        # Create a file-like object for Gemini
                        pdf_file = io.BytesIO(file_data)
                        pdf_file.name = filename or "document.pdf"
                        
                        # Try to upload the PDF directly to Gemini
                        response = model.generate_content([
                            """
                            Analyze this PDF document (bill/receipt/invoice) and extract the following information in JSON format:
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
                            """,
                            pdf_file
                        ])
                        
                        extracted_text = response.text.strip()
                        print("PDF processed directly with Gemini")
                        
                        # Process the response
                        return self._process_gemini_response(extracted_text)
                        
                    except Exception as e:
                        print(f"Direct PDF processing with Gemini failed: {e}")
                
                # If we have an image from PDF conversion, continue with normal processing
                if image is not None:
                    # Convert to RGB if necessary
                    if image.mode != 'RGB':
                        image = image.convert('RGB')
                else:
                    # All PDF processing methods failed
                    print("All PDF processing methods failed")
                    return {
                        "bill_number": None,
                        "bill_date": None,
                        "vendor_name": None,
                        "transaction_category": "Other",
                        "purpose": "PDF processing failed - unable to extract content",
                        "amount": 0,
                        "currency": "INR",
                        "product": "General",
                        "cluster_location": None,
                        "confidence_score": 0
                    }
            else:
                # For non-PDF files (images), process directly
                try:
                    image = Image.open(io.BytesIO(file_data))
                    # Convert to RGB if necessary
                    if image.mode != 'RGB':
                        image = image.convert('RGB')
                    print(f"Image file processed: {filename}")
                except Exception as e:
                    print(f"Error opening file as image: {e}")
                    return {
                        "bill_number": None,
                        "bill_date": None,
                        "vendor_name": None,
                        "transaction_category": "Other",
                        "purpose": "Image processing error",
                        "amount": 0,
                        "currency": "INR",
                        "product": "General",
                        "cluster_location": None,
                        "confidence_score": 0
                    }
            
            # Prepare prompt for OCR extraction
            prompt = """
            Analyze this document (bill/receipt/invoice/document) and extract the following information in JSON format:
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
            - Handle any file format including images, PDFs, documents
            """
            
            print("Sending image to Gemini for analysis...")
            response = model.generate_content([prompt, image])
            extracted_text = response.text.strip()
            print("Gemini analysis completed")
            
            # Process the response
            return self._process_gemini_response(extracted_text)
                
        except Exception as e:
            print(f"OCR Error: {str(e)}")
            return {
                "bill_number": None,
                "bill_date": None,
                "vendor_name": None,
                "transaction_category": "Other",
                "purpose": "Bill processing error",
                "amount": 0,
                "currency": "INR",
                "product": "General",
                "cluster_location": None,
                "confidence_score": 0
            }
    
    def _process_gemini_response(self, extracted_text):
        """Process and parse Gemini API response"""
        try:
            print(f"Processing Gemini response: {extracted_text[:200]}...")
            
            # Clean and parse JSON response
            if extracted_text.startswith('```json'):
                extracted_text = extracted_text[7:-3]
            elif extracted_text.startswith('```'):
                extracted_text = extracted_text[3:-3]
            
            try:
                bill_data = json.loads(extracted_text)
                print("Successfully parsed JSON response")
                
                # Validate and clean the extracted data
                validated_data = {
                    "bill_number": bill_data.get('bill_number'),
                    "bill_date": bill_data.get('bill_date'),
                    "vendor_name": bill_data.get('vendor_name'),
                    "transaction_category": bill_data.get('transaction_category', 'Other'),
                    "purpose": bill_data.get('purpose', 'Bill processing'),
                    "amount": float(bill_data.get('amount', 0)) if bill_data.get('amount') else 0,
                    "currency": bill_data.get('currency', 'INR'),
                    "product": bill_data.get('product', 'General'),
                    "cluster_location": bill_data.get('cluster_location'),
                    "confidence_score": int(bill_data.get('confidence_score', 50)) if bill_data.get('confidence_score') else 50
                }
                
                print(f"Extraction successful - Amount: {validated_data['amount']}, Vendor: {validated_data['vendor_name']}")
                return validated_data
                
            except json.JSONDecodeError as e:
                print(f"JSON parsing failed: {e}")
                # Try to extract data using regex as fallback
                return self._fallback_text_extraction(extracted_text)
                
        except Exception as e:
            print(f"Response processing error: {e}")
            return {
                "bill_number": None,
                "bill_date": None,
                "vendor_name": None,
                "transaction_category": "Other",
                "purpose": "Response processing error",
                "amount": 0,
                "currency": "INR",
                "product": "General",
                "cluster_location": None,
                "confidence_score": 25
            }
    
    def _fallback_text_extraction(self, text):
        """Fallback method to extract data from unstructured text"""
        import re
        
        print("Using fallback text extraction...")
        
        result = {
            "bill_number": None,
            "bill_date": None,
            "vendor_name": None,
            "transaction_category": "Other",
            "purpose": "Text extraction fallback",
            "amount": 0,
            "currency": "INR",
            "product": "General",
            "cluster_location": None,
            "confidence_score": 30
        }
        
        try:
            # Try to extract amount (look for currency symbols and numbers)
            amount_patterns = [
                r'₹\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
                r'(?:amount|total|sum|price)[\s:]*₹?\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
                r'(\d+(?:,\d+)*(?:\.\d{2})?)\s*₹'
            ]
            
            for pattern in amount_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    amount_str = match.group(1).replace(',', '')
                    result["amount"] = float(amount_str)
                    break
            
            # Try to extract date
            date_patterns = [
                r'(\d{4}-\d{2}-\d{2})',
                r'(\d{2}[-/]\d{2}[-/]\d{4})',
                r'(\d{2}[-/]\d{2}[-/]\d{2})'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    result["bill_date"] = match.group(1)
                    break
            
            print(f"Fallback extraction completed - Amount: {result['amount']}")
            
        except Exception as e:
            print(f"Fallback extraction error: {e}")
        
        return result
    
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
            "remarks": form_data.get('remarks', '')
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
            for i, image_data in enumerate(bill_images):
                extracted_data = self.extract_bill_details(image_data, f"bill_{i}.jpg")
                
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

# Authentication Routes
@app.route('/login')
def login():
    """Render login page"""
    firebase_config = {
        'apiKey': config.FIREBASE_API_KEY,
        'authDomain': config.FIREBASE_AUTH_DOMAIN,
        'projectId': config.FIREBASE_PROJECT_ID,
        'storageBucket': config.FIREBASE_STORAGE_BUCKET,
        'messagingSenderId': config.FIREBASE_MESSAGING_SENDER_ID,
        'appId': config.FIREBASE_APP_ID
    }
    return render_template('login.html', firebase_config=firebase_config)

@app.route('/login/callback', methods=['POST'])
def login_callback():
    """Handle Firebase authentication callback"""
    try:
        print("Login callback called")
        data = request.get_json()
        print(f"Received data: {data}")
        
        id_token = data.get('idToken')
        
        if not id_token:
            print("No ID token provided")
            return jsonify({'success': False, 'error': 'No ID token provided'}), 400
        
        # Verify the Firebase ID token
        user_info = verify_firebase_token(id_token)
        
        if user_info:
            print(f"User authenticated: {user_info.get('email')}")
            # Store user info in session
            session['user'] = {
                'uid': user_info['uid'],
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'picture': user_info.get('picture'),
                'email_verified': user_info.get('email_verified', False)
            }
            
            # Look up employee details
            user_email = user_info.get('email', '').strip().lower()
            employee_details = EMPLOYEE_DATA.get(user_email)
            
            if employee_details:
                session['employee_details'] = {
                    "employee_id": employee_details.get("Employee ID"),
                    "employee_name": employee_details.get("Employee Name"),
                    "employee_email": employee_details.get("Employee Email ID"),
                    "department": employee_details.get("Department Name"),
                    "team": employee_details.get("Team Name"),
                    "hod_name": employee_details.get("Reporting Person - 1 Name"),
                    "hod_email": employee_details.get("Reporting Person - 1 Email"),
                    "reporting_2_name": employee_details.get("Reporting Person - 2 Name"),
                    "reporting_2_email": employee_details.get("Reporting Person - 2 Email"),
                    "reporting_3_name": employee_details.get("Reporting Person - 3 Name"),
                    "reporting_3_email": employee_details.get("Reporting Person - 3 Email"),
                    "phone": employee_details.get("Phone Number of Employee")
                }
                print(f"Employee details loaded for: {employee_details.get('Employee Name')}")
            else:
                session['employee_details'] = None
                print(f"No employee details found for email: {user_email}")
            
            return jsonify({
                'success': True, 
                'redirect_url': url_for('index')
            })
        else:
            print("Token verification failed")
            return jsonify({'success': False, 'error': 'Invalid token or verification failed'}), 401
            
    except Exception as e:
        print(f"Login callback error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/logout')
def logout():
    """Log out user"""
    session.pop('user', None)
    session.pop('employee_details', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard showing profile info"""
    user = session.get('user')
    employee_details = session.get('employee_details')
    return render_template('dashboard.html', user=user, employee_details=employee_details)

@app.route('/')
@login_required
def index():
    user = session.get('user')
    employee_details = session.get('employee_details')
    return render_template('index.html', user=user, employee_details=employee_details)

@app.route('/process-bill', methods=['POST'])
@login_required
def process_bill():
    """Process a single bill and extract details using Gemini Vision API"""
    try:
        if 'bill_image' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['bill_image']
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        if file and allowed_file(file.filename):
            # Read the file data
            file_data = file.read()
            
            # Extract bill details using Gemini (with filename for extension detection)
            bill_details = processor.extract_bill_details(file_data, file.filename)
            
            return jsonify({
                'success': True,
                'bill_details': bill_details
            })
        else:
            return jsonify({'success': False, 'error': 'Invalid file type'}), 400
            
    except Exception as e:
        print(f"Bill processing error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/submit-claim', methods=['POST'])
@login_required
def submit_claim():
    try:
        # Get form data
        form_data = request.form.to_dict()
        
        # Get transaction count
        transaction_count = int(form_data.get('transaction_count', 1))
        
        # Parse transactions
        transactions = []
        total_amount = 0
        
        for i in range(transaction_count):
            transaction = {}
            bill_file = None
            
            # Get transaction data
            for key in ['bill_date', 'bill_number', 'transaction_category', 'purpose', 'amount', 'product', 'cluster', 'remarks']:
                transaction[key] = form_data.get(f'transaction_{i}_{key}', '')
            
            # Get bill file if uploaded
            bill_file_key = f'transaction_{i}_bill'
            if bill_file_key in request.files:
                file = request.files[bill_file_key]
                if file and file.filename and allowed_file(file.filename):
                    bill_file = file.read()
            
            # Convert amount to float
            try:
                transaction['amount'] = float(transaction['amount']) if transaction['amount'] else 0
                total_amount += transaction['amount']
            except (ValueError, TypeError):
                transaction['amount'] = 0
            
            # Add bill file data
            transaction['bill_file'] = bill_file
            transactions.append(transaction)
        
        # Create claim data structure
        claim_data = {
            'employee_name': form_data.get('employee_name', ''),
            'department': form_data.get('department', ''),
            'hod': form_data.get('hod', ''),
            'hod_email': form_data.get('hod_email', ''),
            'cc_emails': form_data.get('cc_emails', ''),
            'payment_mode': form_data.get('payment_mode', 'Bank Transfer'),
            'transactions': transactions,
            'total_amount': total_amount,
            'transaction_count': transaction_count,
            'submission_date': datetime.now().isoformat(),
            'status': 'Pending',
            'submitted_by': session.get('user', {}).get('email', 'Unknown')
        }
        
        # Process each transaction with OCR if bill is provided
        for i, transaction in enumerate(transactions):
            if transaction.get('bill_file'):
                try:
                    extracted_details = processor.extract_bill_details(transaction['bill_file'])
                    transaction['extracted_details'] = extracted_details
                except Exception as e:
                    print(f"Error extracting details for transaction {i}: {e}")
                    transaction['extracted_details'] = None
                
                # Remove the binary data before saving
                transaction['bill_file'] = f"transaction_{i}_bill.jpg"  # Just store filename reference
        
        # Generate claim ID
        import uuid
        claim_id = f"CLAIM_{datetime.now().strftime('%Y%m%d')}_{str(uuid.uuid4())[:8].upper()}"
        claim_data['claim_id'] = claim_id
        
        # Save claim
        processor.processed_claims.append(claim_data)
        processor.save_claims()
        
        return jsonify({
            "success": True,
            "data": {
                "claim_id": claim_id,
                "total_amount": total_amount,
                "transaction_count": transaction_count,
                "status": "Submitted successfully"
            }
        })
        
    except Exception as e:
        print(f"Submit claim error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

@app.route('/claims')
@login_required
def view_claims():
    claims = processor.get_all_claims()
    return render_template('claims.html', claims=claims)

@app.route('/api/claims')
@login_required
def api_claims():
    claims = processor.get_all_claims()
    return jsonify(claims)

@app.route('/api/claims/<claim_id>')
@login_required
def api_claim_detail(claim_id):
    claim = processor.get_claim_by_id(claim_id)
    if claim:
        return jsonify(claim)
    return jsonify({"error": "Claim not found"}), 404

@app.route('/api/claims/<claim_id>', methods=['DELETE'])
@login_required
def api_delete_claim(claim_id):
    if processor.delete_claim(claim_id):
        return jsonify({"success": True, "message": "Claim deleted successfully"})
    return jsonify({"error": "Claim not found"}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)