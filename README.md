# ReimburseFlow - AI-Powered Reimbursement Management System

## Overview
ReimburseFlow is a comprehensive reimbursement claim processing platform designed for NxtWave. It uses Google's Gemini 2.5 Flash AI model for OCR extraction from bill images and provides a complete workflow for multi-level approvals.

## Features

### 🔍 AI-Powered OCR Processing
- Extracts bill details using Google Gemini 2.5 Flash API
- Supports multiple image formats: PNG, JPG, JPEG, PDF, WEBP
- Automatic field extraction: bill number, date, vendor, amount, category
- Confidence scoring for validation

### 📝 Comprehensive Form Handling
- Employee details management
- Department and HOD tracking
- Multiple bill submission support
- "No Bill" option with comment requirements
- Manual entry override capabilities

### ✅ Intelligent Validation
- Duplicate detection based on bill number + vendor + amount
- Change flagging when manual entry differs from OCR
- Low confidence detection (< 85%) for review requirements
- Multi-level approval status tracking

### 🎨 Responsive Frontend
- Built with Tailwind CSS for modern, responsive design
- Drag & drop file upload interface
- Real-time form validation
- Interactive results display
- Mobile-friendly design

### 📊 Claims Management
- View all submitted claims
- Filter by status, department, employee
- Detailed claim inspection
- Summary statistics dashboard
- Local JSON storage for data persistence
- Unique claim ID generation
- Delete claims functionality

## Getting Started

### Prerequisites
- Python 3.8 or higher
- Virtual environment (recommended)

### Installation

1. **Navigate to the project directory:**
   ```bash
   cd reimburse-flow
   ```

2. **Create and activate virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Configuration

The application uses the following environment variables (configured in `config.py`):

- `GEMINI_API_KEY`: Google Gemini API key for OCR processing
- `FLASK_ENV`: Environment setting (development/production)
- `SECRET_KEY`: Flask secret key for sessions
- `UPLOAD_FOLDER`: Directory for temporary file uploads
- `MAX_CONTENT_LENGTH`: Maximum file upload size (16MB)

### Running the Application

1. **Start the development server:**
   ```bash
   source venv/bin/activate
   python app.py
   ```

2. **Access the application:**
   - Open your browser and navigate to: `http://localhost:5001`
   - Submit claims at: `http://localhost:5001/`
   - View claims at: `http://localhost:5001/claims`
   - API endpoint: `http://localhost:5001/api/claims`

## Usage Guide

### Submitting a Claim

1. **Fill Employee Details:**
   - Employee name, department, HOD information
   - Payment mode and CC email addresses

2. **Enter Claim Information:**
   - Transaction category (Travel, Food, Office Supplies, etc.)
   - Purpose, product, cluster location
   - People involved and additional remarks

3. **Upload Bills:**
   - **With Bills**: Drag & drop or click to upload bill images
   - **No Bills**: Select "No Bill Available" and provide explanation

4. **Submit and Review:**
   - Review extracted OCR data
   - Check for any flags or warnings
   - View processing results

### Viewing Claims

1. **Access Claims Dashboard:**
   - Navigate to `/claims` to view all submitted claims
   - Use filters to search by status, department, or employee

2. **Claim Details:**
   - Click "View" to see detailed claim information
   - Review bill-by-bill processing results
   - Check approval status and flags

## API Documentation

### Submit Claim
- **Endpoint**: `POST /submit-claim`
- **Content-Type**: `multipart/form-data`
- **Parameters**: Form data + bill images
- **Response**: JSON with processing results

### Get All Claims
- **Endpoint**: `GET /api/claims`
- **Response**: Array of all processed claims

### Get Specific Claim
- **Endpoint**: `GET /api/claims/{claim_id}`
- **Response**: Individual claim details

### Delete Claim
- **Endpoint**: `DELETE /api/claims/{claim_id}`
- **Response**: Success/failure message

## Output Schema

The system returns structured JSON data following this schema:

```json
{
  "id": "CLM_YYYYMMDD_HHMMSS_XXX",
  "employee_details": {
    "form_filled_by": "string",
    "department": "string", 
    "hod": "string",
    "hod_email": "string",
    "cc_emails": ["string"],
    "additional_cc": ["string"],
    "mode_of_payment": "string"
  },
  "claim_details": {
    "transaction_category": "string",
    "purpose": "string",
    "product": "string", 
    "cluster": "string",
    "remarks": "string",
    "people_involved": ["string"]
  },
  "bills": [
    {
      "bill_number": "string",
      "bill_date": "YYYY-MM-DD",
      "vendor_name": "string",
      "transaction_category": "string", 
      "purpose": "string",
      "amount": number,
      "currency": "string",
      "product": "string",
      "cluster_location": "string",
      "needs_review": boolean,
      "change_flag": boolean,
      "duplicate_detected": boolean,
      "approval_status": "pending|approved|rejected|needs_review",
      "rejection_reason": "string or null"
    }
  ],
  "overall_status": "pending|partially_approved|approved|rejected"
}
```

## Architecture

### Backend (Flask)
- **app.py**: Main Flask application with routes and business logic
- **config.py**: Environment configuration
- **ReimbursementProcessor**: Core class handling OCR and validation

### Frontend (HTML/CSS/JS)
- **templates/base.html**: Base template with navigation and common styling
- **templates/index.html**: Claim submission form with Alpine.js
- **templates/claims.html**: Claims viewing dashboard
- **Tailwind CSS**: For responsive, modern styling
- **Alpine.js**: For reactive frontend behavior

### File Structure
```
reimburse-flow/
├── app.py                 # Main Flask application
├── config.py             # Configuration settings
├── requirements.txt      # Python dependencies
├── run.sh               # Startup script
├── claims_data.json     # Local JSON storage for claims
├── venv/                # Virtual environment
├── uploads/             # Temporary file storage
└── templates/           # HTML templates
    ├── base.html
    ├── index.html
    └── claims.html
```

## Data Storage

### Local JSON Storage
- **File**: `claims_data.json`
- **Format**: Array of claim objects
- **Persistence**: Data survives application restarts
- **Backup**: Manual backup by copying the JSON file

### Data Management
- **Automatic saving**: Claims saved immediately upon submission
- **Unique IDs**: Each claim gets a unique identifier (CLM_YYYYMMDD_HHMMSS_XXX)
- **CRUD operations**: Create, Read, Update, Delete via API endpoints
- **Data integrity**: JSON validation and error handling

## Security Features

- File upload validation (type and size limits)
- CORS protection for API endpoints
- Input sanitization and validation
- Secure file handling with temporary storage
- Local data storage (no external database dependencies)

## Troubleshooting

### Common Issues

1. **Port 5000 in use**: The app runs on port 5001 by default
2. **Import errors**: Ensure virtual environment is activated
3. **API key errors**: Verify Gemini API key in config.py
4. **File upload issues**: Check file size (max 16MB) and format

### Development Tips

- Use debug mode for development (enabled by default)
- Check browser console for JavaScript errors
- Monitor Flask console for backend errors
- Test with various bill image types and qualities

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

© 2025 NxtWave. All rights reserved.

---

**Note**: This system is specifically designed for NxtWave's reimbursement workflow and uses Google's Gemini AI for bill processing. Ensure proper API key configuration before deployment.
