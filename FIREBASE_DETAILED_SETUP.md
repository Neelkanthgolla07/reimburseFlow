# Firebase Setup Guide for Reimbursement Platform

This guide will help you set up Firebase Storage and Firestore for the reimbursement platform.

## Prerequisites

1. A Google account
2. Access to Firebase Console
3. The `firebase_credentials.json` file for your project

## Step 1: Enable Required Services

### 1.1 Enable Firestore Database

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project (`optimal-analogy-394213`)
3. In the left sidebar, click **Firestore Database**
4. Click **Create database**
5. Choose **Start in test mode** (you can change security rules later)
6. Select a location (choose the one closest to your users)
7. Click **Done**

### 1.2 Enable Firebase Storage

1. In the Firebase Console, click **Storage** in the left sidebar
2. Click **Get started**
3. Choose **Start in test mode** (you can change security rules later)
4. Select the same location as your Firestore database
5. Click **Done**

## Step 2: Configure Security Rules

### 2.1 Firestore Security Rules

1. Go to **Firestore Database** > **Rules**
2. Replace the default rules with:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Allow authenticated users to read/write their own claims
    match /reimbursement_claims/{document} {
      allow read, write: if request.auth != null && 
        (request.auth.token.email == resource.data.employee_details.employee_email ||
         request.auth.token.email == resource.data.metadata.submitted_by);
    }
    
    // Allow authenticated users to read/write their own data
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
  }
}
```

3. Click **Publish**

### 2.2 Storage Security Rules

1. Go to **Storage** > **Rules**
2. Replace the default rules with:

```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    // Allow authenticated users to upload files to claims folder
    match /claims/{allPaths=**} {
      allow read, write: if request.auth != null;
    }
  }
}
```

3. Click **Publish**

## Step 3: Configure Authentication

### 3.1 Enable Google Sign-In

1. Go to **Authentication** in the left sidebar
2. Click **Get started**
3. Go to the **Sign-in method** tab
4. Click on **Google**
5. Toggle **Enable**
6. Add your domain to **Authorized domains** if needed
7. Click **Save**

### 3.2 Configure OAuth Consent Screen

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project
3. Go to **APIs & Services** > **OAuth consent screen**
4. Choose **External** user type (to allow any Google account)
5. Fill in the required information:
   - App name: "Reimbursement Platform"
   - User support email: Your email
   - Developer contact information: Your email
6. Click **Save and Continue**
7. Skip **Scopes** (click **Save and Continue**)
8. Add test users if needed
9. Click **Save and Continue**

## Step 4: Verify Configuration

### 4.1 Test Database Connection

1. Start your application: `python app.py`
2. Check the console for these messages:
   - "Firebase Admin SDK initialized successfully"
   - "Firestore client initialized successfully"
   - "Firebase Storage bucket initialized successfully"

### 4.2 Test File Upload

1. Go to your application
2. Log in with a Google account
3. Submit a claim with a file attachment
4. Check Firebase Storage to see if the file was uploaded
5. Check Firestore to see if the claim data was saved

## Step 5: Production Considerations

### 5.1 Security Rules

For production, update the security rules to be more restrictive:

```javascript
// Example: Only allow users with specific domain
allow read, write: if request.auth != null && 
  request.auth.token.email.matches('.*@yourcompany\\.com$');
```

### 5.2 File Size Limits

The current implementation has a 16MB limit. You can adjust this in:
- `config.py`: `MAX_CONTENT_LENGTH`
- Frontend validation in `index.html`

### 5.3 Storage Costs

Monitor your Firebase usage:
- Firestore: Charged per read/write/delete operation
- Storage: Charged per GB stored and bandwidth used

## Troubleshooting

### Common Issues

1. **"Firebase services not available"**
   - Check if `firebase_credentials.json` exists
   - Verify the file is valid JSON
   - Check console for initialization errors

2. **"Permission denied" errors**
   - Verify security rules are published
   - Check if user is properly authenticated
   - Ensure user email matches the rules

3. **File upload failures**
   - Check file size (max 16MB)
   - Verify Storage is enabled
   - Check Storage security rules

### Debug Mode

Add this to your `.env` file for more verbose logging:
```
FLASK_DEBUG=True
```

## Support

If you encounter issues:
1. Check the browser console for JavaScript errors
2. Check the Flask console for Python errors
3. Verify all Firebase services are enabled
4. Check Firebase Console logs for any errors
