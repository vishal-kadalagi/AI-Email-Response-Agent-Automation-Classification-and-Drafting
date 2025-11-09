# 💌 AI Email Reply & Automation Agent (Tkinter GUI)

> ✨ A desktop-based intelligent email assistant that fetches unread emails, classifies them by priority, and generates smart replies automatically using a local language model — all in a single Python file.

---

## 🚀 Features

✅ **Fetch Unread Emails** – Connects securely via IMAP and lists unread emails.  
🤖 **AI Reply Generator** – Generates concise replies using HuggingFace transformers (GPT-based).  
📊 **Email Categorization** – Automatically classifies emails as *Urgent*, *Needs Reply*, or *Informational*.  
📝 **Save Reply Drafts** – Stores AI-generated replies for future use.  
🎨 **Simple Tkinter GUI** – Clean, responsive interface built entirely in Python.  
🔒 **Offline Fallback** – Works even without AI libraries using predefined smart templates.

---

## 🧠 How It Works

1. Connects to your **Gmail inbox** securely using IMAP.  
2. Fetches unread messages (up to 30 by default).  
3. Uses keyword-based classification to categorize emails.  
4. Generates reply text using a **tiny GPT-2 model** (or fallback templates).  
5. Allows you to **edit, review, and save** replies as drafts.

---

## 🧰 Requirements

Before running, install dependencies:

```bash
pip install imapclient transformers torch requests beautifulsoup4
