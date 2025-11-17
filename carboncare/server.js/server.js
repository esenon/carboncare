/*
Small Express backend (single-file) providing:
 - account creation (name, email, password)
 - basic name + email validation
 - email verification (token sent via SMTP)
 - simple login (only if email verified)

Instructions (short):
 1. create a project folder and put this file as server.js
 2. run: npm init -y
 3. install: npm i express sqlite3 bcrypt nodemailer body-parser dotenv
 4. set environment variables in a .env file:
    PORT=3000
    BASE_URL=http://localhost:3000
    SMTP_HOST=smtp.example.com
    SMTP_PORT=587
    SMTP_USER=you@example.com
    SMTP_PASS=yourpassword
 5. run: node server.js

Endpoints:
 POST /register   { name, email, password }
 GET  /verify?token=...   (email verification link)
 POST /login      { email, password }
 POST /resend     { email }

This is intentionally small and easy to extend.
*/

require('dotenv').config();
const express = require('express');
const bodyParser = require('body-parser');
const sqlite3 = require('sqlite3').verbose();
const bcrypt = require('bcrypt');
const crypto = require('crypto');
const nodemailer = require('nodemailer');

const app = express();
app.use(bodyParser.json());

const PORT = process.env.PORT || 3000;
const BASE_URL = process.env.BASE_URL || `http://localhost:${PORT}`;

// --- Database (SQLite, file-based) ---
const db = new sqlite3.Database('./users.db', (err) => {
  if (err) return console.error('Failed to open DB', err);
});

// Create users table
db.run(`
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  is_verified INTEGER NOT NULL DEFAULT 0,
  verify_token TEXT,
  verify_token_expires INTEGER
)
`);

// --- Mailer setup (nodemailer) ---
const transporter = nodemailer.createTransport({
  host: process.env.SMTP_HOST,
  port: parseInt(process.env.SMTP_PORT || '587', 10),
  secure: false,
  auth: {
    user: process.env.SMTP_USER,
    pass: process.env.SMTP_PASS,
  },
});

// Helper: send verification email (returns a Promise)
function sendVerificationEmail(email, token) {
  const verifyUrl = `${BASE_URL}/verify?token=${encodeURIComponent(token)}`;
  const mailOptions = {
    from: process.env.SMTP_USER,
    to: email,
    subject: 'Verify your email',
    text: `Please verify your email by clicking the link: ${verifyUrl}`,
    html: `<p>Please verify your email by clicking the link below:</p><p><a href="${verifyUrl}">${verifyUrl}</a></p>`,
  };
  return transporter.sendMail(mailOptions);
}

// --- Validation helpers ---
function validateName(name) {
  if (!name || typeof name !== 'string') return 'Name is required';
  const s = name.trim();
  if (s.length < 2) return 'Name must be at least 2 characters';
  // allow letters, spaces, hyphens, apostrophes
  if (!/^[A-Za-z\s\-']+$/.test(s)) return 'Name contains invalid characters';
  return null;
}

function validateEmail(email) {
  if (!email || typeof email !== 'string') return 'Email is required';
  const s = email.trim().toLowerCase();
  // simple email regex (sufficient for small projects)
  if (!/^\S+@\S+\.\S+$/.test(s)) return 'Email is invalid';
  return null;
}

function validatePassword(pw) {
  if (!pw || typeof pw !== 'string') return 'Password is required';
  if (pw.length < 6) return 'Password must be at least 6 characters';
  return null;
}

// --- Routes ---
app.post('/register', async (req, res) => {
  try {
    const { name, email, password } = req.body;
    // validation
    const nameErr = validateName(name);
    if (nameErr) return res.status(400).json({ error: nameErr });
    const emailErr = validateEmail(email);
    if (emailErr) return res.status(400).json({ error: emailErr });
    const pwErr = validatePassword(password);
    if (pwErr) return res.status(400).json({ error: pwErr });

    const emailNorm = email.trim().toLowerCase();

    // check existing
    db.get('SELECT id FROM users WHERE email = ?', [emailNorm], async (err, row) => {
      if (err) return res.status(500).json({ error: 'DB error' });
      if (row) return res.status(409).json({ error: 'Email already registered' });

      const hash = await bcrypt.hash(password, 10);
      const token = crypto.randomBytes(24).toString('hex');
      const expires = Date.now() + 24 * 60 * 60 * 1000; // 24 hours

      db.run(
        `INSERT INTO users (name, email, password_hash, verify_token, verify_token_expires) VALUES (?,?,?,?,?)`,
        [name.trim(), emailNorm, hash, token, expires],
        function (insertErr) {
          if (insertErr) return res.status(500).json({ error: 'DB insert error' });

          // send email (fire-and-forget but handle error)
          sendVerificationEmail(emailNorm, token)
            .then(() => {
              return res.status(201).json({ message: 'Account created. Verification email sent.' });
            })
            .catch((mailErr) => {
              console.error('Mail error:', mailErr);
              // still return success but warn user to check spam or contact admin
              return res.status(201).json({ message: 'Account created but failed to send verification email. Contact admin.' });
            });
        }
      );
    });
  } catch (e) {
    console.error(e);
    return res.status(500).json({ error: 'Server error' });
  }
});

app.get('/verify', (req, res) => {
  const token = req.query.token;
  if (!token) return res.status(400).send('Missing token');

  db.get('SELECT id, verify_token_expires FROM users WHERE verify_token = ?', [token], (err, row) => {
    if (err) return res.status(500).send('DB error');
    if (!row) return res.status(400).send('Invalid token');
    if (Date.now() > row.verify_token_expires) return res.status(400).send('Token expired');

    db.run('UPDATE users SET is_verified = 1, verify_token = NULL, verify_token_expires = NULL WHERE id = ?', [row.id], (uerr) => {
      if (uerr) return res.status(500).send('DB update error');
      return res.send('Email verified successfully! You may now log in.');
    });
  });
});

app.post('/resend', (req, res) => {
  const { email } = req.body;
  const emailNorm = (email || '').trim().toLowerCase();
  const emailErr = validateEmail(emailNorm);
  if (emailErr) return res.status(400).json({ error: emailErr });

  db.get('SELECT id, is_verified FROM users WHERE email = ?', [emailNorm], (err, row) => {
    if (err) return res.status(500).json({ error: 'DB error' });
    if (!row) return res.status(404).json({ error: 'No account with that email' });
    if (row.is_verified) return res.status(400).json({ error: 'Account already verified' });

    const token = crypto.randomBytes(24).toString('hex');
    const expires = Date.now() + 24 * 60 * 60 * 1000;
    db.run('UPDATE users SET verify_token = ?, verify_token_expires = ? WHERE id = ?', [token, expires, row.id], (uerr) => {
      if (uerr) return res.status(500).json({ error: 'DB update error' });
      sendVerificationEmail(emailNorm, token)
        .then(() => res.json({ message: 'Verification email resent' }))
        .catch((mailErr) => {
          console.error(mailErr);
          res.status(500).json({ error: 'Failed to send email' });
        });
    });
  });
});

app.post('/login', (req, res) => {
  const { email, password } = req.body;
  const emailNorm = (email || '').trim().toLowerCase();
  if (!emailNorm || !password) return res.status(400).json({ error: 'Email and password required' });

  db.get('SELECT id, password_hash, is_verified, name FROM users WHERE email = ?', [emailNorm], async (err, row) => {
    if (err) return res.status(500).json({ error: 'DB error' });
    if (!row) return res.status(401).json({ error: 'Invalid credentials' });

    const ok = await bcrypt.compare(password, row.password_hash);
    if (!ok) return res.status(401).json({ error: 'Invalid credentials' });
    if (!row.is_verified) return res.status(403).json({ error: 'Email not verified' });

    // For simplicity we return a small session object. Replace with JWT or session for production.
    return res.json({ message: 'Login successful', user: { id: row.id, name: row.name, email: emailNorm } });
  });
});

// Simple health check
app.get('/', (req, res) => res.send('Small account backend running'));

app.listen(PORT, () => console.log(`Server listening on port ${PORT}`));
