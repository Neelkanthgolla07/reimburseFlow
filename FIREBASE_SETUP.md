# Firebase Authentication Setup Instructions

This document provides step-by-step instructions to complete the Firebase authentication setup for your ReimburseFlow application.

## Prerequisites

1. You should have a Firebase project set up with the provided configuration
2. Google Authentication should be enabled in your Firebase Console

## Setup Steps

### 1. Install Dependencies

The required dependencies have been added to `requirements.txt`. Install them using:

```bash
pip install -r requirements.txt
```

### 2. Firebase Service Account Credentials

You need to download the Firebase Admin SDK service account key:

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project: `reimbursement-app-bbad3`
3. Go to Project Settings (gear icon) → Service Accounts
4. Click "Generate new private key"
5. Download the JSON file
6. Rename it to `firebase_credentials.json`
7. Place it in the root directory of your project

**Important**: Never commit this file to version control. Add it to `.gitignore`.

### 3. Enable Google Authentication

1. In Firebase Console, go to Authentication → Sign-in method
2. Enable Google sign-in provider
3. Add your domain to authorized domains if running in production

### 4. Test the Setup

1. Start your Flask application:
   ```bash
   python app.py
   ```

2. Navigate to `http://localhost:5001/login`
3. Try signing in with Google
4. After successful login, you should be redirected to the main page
5. Visit `http://localhost:5001/dashboard` to see your profile

## New Routes Added

- `/login` - Login page with Google sign-in
- `/login/callback` - Handles Firebase authentication
- `/logout` - Logs out the user
- `/dashboard` - User profile dashboard (requires login)

## Security Features

- Firebase ID token verification
- Session-based user management
- Login required decorator for protected routes
- Secure user data storage

## Template Updates

- `base.html` - Updated navigation with login/logout options
- `login.html` - New login page with Google authentication
- `dashboard.html` - New user dashboard showing profile information

## Configuration

All Firebase configuration is stored in `config.py`:

```python
# Firebase Web Config (for frontend)
FIREBASE_API_KEY = "AIzaSyBBhrPZQlbNliuDX0wHB6jRBa1ZW7X_F-k"
FIREBASE_AUTH_DOMAIN = "reimbursement-app-bbad3.firebaseapp.com"
FIREBASE_PROJECT_ID = "reimbursement-app-bbad3"
FIREBASE_STORAGE_BUCKET = "reimbursement-app-bbad3.firebasestorage.app"
FIREBASE_MESSAGING_SENDER_ID = "788254782022"
FIREBASE_APP_ID = "1:788254782022:web:850b329362e0716c4a1047"

# Firebase Admin SDK Config
FIREBASE_CREDENTIALS_PATH = "firebase_credentials.json"
```

## Adding Authentication to Existing Routes

To protect any existing route with authentication, simply add the `@login_required` decorator:

```python
@app.route('/protected-route')
@login_required
def protected_route():
    # This route now requires authentication
    user = session.get('user')
    return render_template('template.html', user=user)
```

## User Session Data

After login, user information is stored in the session:

```python
session['user'] = {
    'uid': user_info['uid'],
    'email': user_info.get('email'),
    'name': user_info.get('name'),
    'picture': user_info.get('picture'),
    'email_verified': user_info.get('email_verified', False)
}
```

## Troubleshooting

### Common Issues:

1. **"Firebase Admin SDK initialization failed"**
   - Ensure `firebase_credentials.json` exists and has correct permissions
   - Verify the service account key is valid

2. **"Authentication failed"**
   - Check that Google sign-in is enabled in Firebase Console
   - Verify Firebase configuration matches your project

3. **"Popup blocked"**
   - Allow popups in your browser for the application domain

4. **CORS Issues**
   - Ensure Flask-CORS is properly configured
   - Add your domain to Firebase authorized domains

## Security Notes

- The `firebase_credentials.json` file contains sensitive information
- Never expose Firebase configuration keys in client-side code (they're safe in templates as they're meant for frontend use)
- Always use HTTPS in production
- Consider implementing additional security measures like rate limiting

## Next Steps

- Add user role management if needed
- Implement password reset functionality
- Add email verification flows
- Set up user profile editing capabilities
- Add audit logging for authentication events

## Support

If you encounter any issues:
1. Check the Flask application logs
2. Verify Firebase Console for authentication events
3. Ensure all dependencies are installed correctly
4. Check browser console for JavaScript errors
