"""
email_agent_gui.py
AI Email Reply & Automation Agent (Tkinter GUI) - Single file

Placeholders:
 - EMAIL_ADDRESS = "your.email@gmail.com"
 - APP_PASSWORD = "your_app_password"

Requirements:
 pip install imapclient transformers torch requests beautifulsoup4

Run:
 python email_agent_gui.py
"""

import json
import threading
import os
from imapclient import IMAPClient
import email
from email.header import decode_header
import tkinter as tk
from tkinter import messagebox, scrolledtext
from datetime import datetime
from bs4 import BeautifulSoup

# Attempt to import transformers
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
    TRANSFORMERS_AVAILABLE = True
except:
    TRANSFORMERS_AVAILABLE = False
    print("Transformers library not available. Will fallback to template replies.")

# ----------------- Config -----------------
EMAIL_ADDRESS = "add your mail here"
APP_PASSWORD = "add your email password here"
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
FETCH_LIMIT = 30
MODEL_NAME = "sshleifer/tiny-gpt2"
DRAFTS_FILE = "email_drafts.json"

# ----------------- Helper functions -----------------
def save_draft(draft):
    drafts = []
    if os.path.exists(DRAFTS_FILE):
        try:
            with open(DRAFTS_FILE, "r", encoding="utf-8") as f:
                drafts = json.load(f)
        except:
            drafts = []
    drafts.append(draft)
    with open(DRAFTS_FILE, "w", encoding="utf-8") as f:
        json.dump(drafts, f, indent=2, ensure_ascii=False)

def decode_mime_words(s):
    if not s:
        return ""
    parts = decode_header(s)
    decoded = ""
    for text, encoding in parts:
        if isinstance(text, bytes):
            try:
                decoded += text.decode(encoding or "utf-8", errors="ignore")
            except:
                decoded += text.decode("utf-8", errors="ignore")
        else:
            decoded += text
    return decoded

def extract_text_from_html(html_content):
    """Convert HTML email body to plain text"""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        # Remove scripts/styles
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)
    except:
        return html_content  # fallback

def simple_classify(subject, body):
    """
    Keyword-based classification: Urgent, Needs Reply, Informational
    """
    text = (subject or "") + " " + (body or "")
    text = text.lower()
    urgent_keywords = ["urgent", "asap", "immediately", "deadline", "important", "critical", "server down", "outage"]
    reply_keywords = ["question", "inquire", "could you", "can you", "please", "request", "action required", "follow up"]
    u = sum(1 for k in urgent_keywords if k in text)
    r = sum(1 for k in reply_keywords if k in text)
    if u >= 1:
        return "Urgent"
    if r >= 1:
        return "Needs Reply"
    return "Informational"

# ----------------- Model wrapper -----------------
class LocalReplyGenerator:
    def __init__(self, model_name=MODEL_NAME):
        self.model_name = model_name
        self.generator = None
        self.tokenizer = None
        self.load_error = None
        if TRANSFORMERS_AVAILABLE:
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self.model = AutoModelForCausalLM.from_pretrained(self.model_name)
                self.generator = pipeline("text-generation", model=self.model, tokenizer=self.tokenizer)
            except Exception as e:
                self.load_error = str(e)
                self.generator = None
                print("Model load error:", e)
        else:
            self.load_error = "transformers library not installed."

    def generate_reply(self, sender_name, subject, body, max_length=150):
        prompt = (
            f"You are a helpful, professional assistant. "
            f"Write a concise reply email to {sender_name} about the following message.\n\n"
            f"Subject: {subject}\n\n"
            f"Message: {body}\n\n"
            f"Reply:"
        )
        if self.generator:
            try:
                raw = self.generator(prompt, max_length=max_length, num_return_sequences=1, do_sample=True, top_k=50)
                text = raw[0]["generated_text"]
                if "Reply:" in text:
                    text = text.split("Reply:")[-1].strip()
                reply = text.strip().split("\n\n")[0]
                if len(reply) < 10:
                    raise ValueError("Generated reply too short")
                if not any(close in reply.lower() for close in ["regards", "thank", "best", "sincerely"]):
                    reply = reply.strip() + "\n\nRegards,\n"
                return reply
            except Exception as e:
                print("Generation error:", e)
        fallback = (
            f"Hi {sender_name or 'there'},\n\n"
            f"Thanks for your message about \"{subject}\". I appreciate you reaching out. "
            f"I'll look into this and get back to you shortly.\n\n"
            f"Best regards,\n"
        )
        return fallback

# ----------------- IMAP fetch -----------------
def fetch_unread_emails(limit=FETCH_LIMIT):
    emails = []
    try:
        with IMAPClient(IMAP_SERVER, port=IMAP_PORT, use_uid=True, ssl=True) as server:
            server.login(EMAIL_ADDRESS, APP_PASSWORD)
            server.select_folder("INBOX")
            uids = server.search(["UNSEEN"])
            uids = sorted(uids, reverse=True)[:limit]
            if not uids:
                return emails
            raw_messages = server.fetch(uids, ["RFC822"])
            for uid in uids:
                msg_data = raw_messages.get(uid)
                if not msg_data:
                    continue
                raw = msg_data.get(b"RFC822")
                if not raw:
                    continue
                msg = email.message_from_bytes(raw)
                subject = decode_mime_words(msg.get("Subject", ""))
                from_ = decode_mime_words(msg.get("From", ""))
                sender_name = from_
                date = msg.get("Date", "")
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        disp = str(part.get("Content-Disposition"))
                        if content_type == "text/plain" and "attachment" not in disp:
                            try:
                                body += part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
                            except:
                                body += part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        elif content_type == "text/html" and "attachment" not in disp and not body:
                            try:
                                html_content = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
                                body = extract_text_from_html(html_content)
                            except:
                                pass
                else:
                    try:
                        body = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")
                    except:
                        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                body_preview = body.strip()
                if len(body_preview) > 2000:
                    body_preview = body_preview[:2000] + "\n\n...[truncated]"
                emails.append({
                    "uid": uid,
                    "from": from_,
                    "sender_name": sender_name,
                    "subject": subject,
                    "body": body_preview,
                    "date": date
                })
    except Exception as e:
        print("IMAP fetch error:", e)
        raise e
    return emails

# ----------------- GUI -----------------
class EmailAgentGUI:
    def __init__(self, root):
        self.root = root
        root.title("AI Email Reply & Automation Agent")
        root.geometry("1000x700")
        root.configure(bg="#f0f2f5")

        self.generator = None
        self.emails = []
        self.selected_index = None

        # ---------------- Top Frame ----------------
        top_frame = tk.Frame(root, bg="#f0f2f5")
        top_frame.pack(fill=tk.X, padx=10, pady=8)

        self.fetch_btn = tk.Button(top_frame, text="Fetch Emails", bg="#4caf50", fg="white", command=self.fetch_emails_thread)
        self.fetch_btn.pack(side=tk.LEFT, padx=4)

        self.analyze_btn = tk.Button(top_frame, text="Analyze & Categorize", bg="#ff9800", fg="white", command=self.analyze_emails, state=tk.DISABLED)
        self.analyze_btn.pack(side=tk.LEFT, padx=4)

        self.generate_btn = tk.Button(top_frame, text="Generate Reply", bg="#2196f3", fg="white", command=self.generate_reply_thread, state=tk.DISABLED)
        self.generate_btn.pack(side=tk.LEFT, padx=4)

        self.save_draft_btn = tk.Button(top_frame, text="Save Draft", bg="#9c27b0", fg="white", command=self.save_selected_draft, state=tk.DISABLED)
        self.save_draft_btn.pack(side=tk.LEFT, padx=4)

        self.status_label = tk.Label(top_frame, text="Ready", bg="#f0f2f5")
        self.status_label.pack(side=tk.RIGHT, padx=4)

        # ---------------- Left Frame ----------------
        left_frame = tk.Frame(root, bg="#f0f2f5")
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=6)

        tk.Label(left_frame, text="Unread Emails", bg="#f0f2f5", font=("Helvetica", 12, "bold")).pack()
        self.email_listbox = tk.Listbox(left_frame, width=70, height=28)
        self.email_listbox.pack(side=tk.LEFT, fill=tk.Y)
        self.email_listbox.bind("<<ListboxSelect>>", self.on_select_email)

        # ---------------- Right Frame ----------------
        right_frame = tk.Frame(root, bg="#f0f2f5")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=6)

        tk.Label(right_frame, text="Email Details", bg="#f0f2f5", font=("Helvetica", 12, "bold")).pack(anchor="w")
        self.details_box = scrolledtext.ScrolledText(right_frame, width=80, height=14, wrap=tk.WORD)
        self.details_box.pack(fill=tk.BOTH, expand=False)
        self.details_box.tag_config("Urgent", foreground="red", font=("Helvetica", 10, "bold"))
        self.details_box.tag_config("Needs Reply", foreground="orange", font=("Helvetica", 10, "bold"))
        self.details_box.tag_config("Informational", foreground="green", font=("Helvetica", 10, "bold"))

        tk.Label(right_frame, text="Generated Reply (editable)", bg="#f0f2f5", font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(8,0))
        self.reply_box = scrolledtext.ScrolledText(right_frame, width=80, height=12, wrap=tk.WORD)
        self.reply_box.pack(fill=tk.BOTH, expand=True)

        bottom_frame = tk.Frame(root, bg="#f0f2f5")
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=6)
        tk.Label(bottom_frame, text="Instructions: Load model → Fetch Emails → Analyze → Select → Generate Reply", bg="#f0f2f5").pack(anchor="w")

        if not os.path.exists(DRAFTS_FILE):
            with open(DRAFTS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)

    # ----------------- Status -----------------
    def set_status(self, text):
        self.status_label.config(text=text)
        self.root.update_idletasks()

    # ----------------- Threads -----------------
    def fetch_emails_thread(self):
        t = threading.Thread(target=self.fetch_emails)
        t.daemon = True
        t.start()

    def load_model_thread(self):
        t = threading.Thread(target=self.load_model)
        t.daemon = True
        t.start()

    def generate_reply_thread(self):
        t = threading.Thread(target=self.generate_reply_for_selected)
        t.daemon = True
        t.start()

    # ----------------- Model -----------------
    def load_model(self):
        self.set_status("Loading local reply model...")
        try:
            self.generator = LocalReplyGenerator(MODEL_NAME)
            if self.generator.load_error:
                messagebox.showwarning("Model Load Warning", f"{self.generator.load_error}\nFallback to template.")
            else:
                messagebox.showinfo("Model Loaded", "Local reply model loaded successfully.")
        except Exception as e:
            messagebox.showerror("Model Error", f"Failed to load model: {e}")
            self.generator = None
        self.set_status("Ready")

    # ----------------- Fetch Emails -----------------
    def fetch_emails(self):
        self.set_status("Fetching unread emails...")
        self.fetch_btn.config(state=tk.DISABLED)
        try:
            emails = fetch_unread_emails(limit=FETCH_LIMIT)
            self.emails = emails
            self.email_listbox.delete(0, tk.END)
            if not emails:
                messagebox.showinfo("No Unread", "No unread emails found.")
            for idx, e in enumerate(emails):
                subj = e.get("subject") or "(No Subject)"
                frm = e.get("from") or "Unknown"
                date = e.get("date") or ""
                display = f"{idx+1}. {subj} — {frm} [{date}]"
                self.email_listbox.insert(tk.END, display)
            self.analyze_btn.config(state=tk.NORMAL if emails else tk.DISABLED)
        except Exception as exc:
            messagebox.showerror("Fetch Error", f"Error fetching emails:\n{exc}")
        finally:
            self.fetch_btn.config(state=tk.NORMAL)
            self.set_status("Ready")

    # ----------------- Analyze -----------------
    def analyze_emails(self):
        if not self.emails:
            messagebox.showinfo("No Emails", "Fetch emails first.")
            return
        for idx, e in enumerate(self.emails):
            cat = simple_classify(e.get("subject", ""), e.get("body", ""))
            e["category"] = cat
            subj = e.get("subject") or "(No Subject)"
            frm = e.get("from") or "Unknown"
            date = e.get("date") or ""
            display = f"{idx+1}. [{cat}] {subj} — {frm} [{date}]"
            self.email_listbox.delete(idx)
            self.email_listbox.insert(idx, display)
        messagebox.showinfo("Analysis Complete", "Emails categorized.")
        self.generate_btn.config(state=tk.NORMAL)

    # ----------------- Select Email -----------------
    def on_select_email(self, event):
        sel = event.widget.curselection()
        if not sel:
            return
        index = sel[0]
        self.selected_index = index
        e = self.emails[index]
        category = e.get("category", "Uncategorized")
        details = (
            f"From: {e.get('from')}\n"
            f"Date: {e.get('date')}\n"
            f"Subject: {e.get('subject')}\n"
            f"Category: {category}\n\n"
            f"{e.get('body')}\n"
        )
        self.details_box.delete(1.0, tk.END)
        self.details_box.insert(tk.END, details)

        # Highlight category keywords
        self.highlight_keywords(self.details_box, e.get("body"), category)

        self.reply_box.delete(1.0, tk.END)
        self.save_draft_btn.config(state=tk.DISABLED)

    # ----------------- Highlight Keywords -----------------
    def highlight_keywords(self, text_widget, body, category):
        urgent_keywords = ["urgent", "asap", "immediately", "deadline", "important", "critical", "server down", "outage"]
        reply_keywords = ["question", "inquire", "could you", "can you", "please", "request", "action required", "follow up"]

        text_widget.tag_remove("UrgentKW", "1.0", tk.END)
        text_widget.tag_remove("ReplyKW", "1.0", tk.END)

        if category == "Urgent":
            keywords = urgent_keywords
            tag = "UrgentKW"
        elif category == "Needs Reply":
            keywords = reply_keywords
            tag = "ReplyKW"
        else:
            return  # no highlights for informational

        for kw in keywords:
            start_idx = "1.0"
            while True:
                pos = text_widget.search(kw, start_idx, stopindex=tk.END, nocase=True)
                if not pos:
                    break
                end_pos = f"{pos}+{len(kw)}c"
                text_widget.tag_add(tag, pos, end_pos)
                start_idx = end_pos

        text_widget.tag_config("UrgentKW", foreground="red", font=("Helvetica", 10, "bold"))
        text_widget.tag_config("ReplyKW", foreground="orange", font=("Helvetica", 10, "bold"))

    # ----------------- Generate Reply -----------------
    def generate_reply_for_selected(self):
        if self.selected_index is None:
            messagebox.showinfo("Select Email", "Select an email first.")
            return
        self.set_status("Generating reply...")
        self.generate_btn.config(state=tk.DISABLED)
        idx = self.selected_index
        e = self.emails[idx]
        sender_name = e.get("sender_name") or e.get("from") or "there"
        subject = e.get("subject") or ""
        body = e.get("body") or ""
        if self.generator is None:
            self.generator = LocalReplyGenerator(MODEL_NAME)
        reply_text = self.generator.generate_reply(sender_name, subject, body)
        self.reply_box.delete(1.0, tk.END)
        self.reply_box.insert(tk.END, reply_text)
        self.save_draft_btn.config(state=tk.NORMAL)
        self.generate_btn.config(state=tk.NORMAL)
        self.set_status("Ready")

    # ----------------- Save Draft -----------------
    def save_selected_draft(self):
        if self.selected_index is None:
            return
        reply_text = self.reply_box.get(1.0, tk.END).strip()
        if not reply_text:
            messagebox.showinfo("Empty Reply", "Cannot save empty reply.")
            return
        e = self.emails[self.selected_index]
        draft = {
            "from": e.get("from"),
            "subject": e.get("subject"),
            "body": e.get("body"),
            "reply": reply_text,
            "category": e.get("category"),
            "saved_at": datetime.now().isoformat()
        }
        save_draft(draft)
        messagebox.showinfo("Draft Saved", "Reply draft saved successfully.")
        self.save_draft_btn.config(state=tk.DISABLED)

# ----------------- Main -----------------
def main():
    root = tk.Tk()
    app = EmailAgentGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
