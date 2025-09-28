"""
StraightUp Modern Desktop App - Pure Tkinter
Beautiful desktop interface matching the web UI design (no CustomTkinter dependency)
Project: perfect-entry-473503-j1
"""

import tkinter as tk
from tkinter import ttk, messagebox, font
import threading
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# ---------- Supabase setup ----------
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    print("❌ SUPABASE_URL or SUPABASE_ANON_KEY missing.")
    print("Create a .env next to tkinter_app.py with:")
    print("SUPABASE_URL=https://YOUR-PROJECT.supabase.co")
    print("SUPABASE_ANON_KEY=YOUR-ANON-KEY")
    raise SystemExit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

class AuthState:
    def __init__(self):
        self.session = None
        self.user = None

    def is_authenticated(self) -> bool:
        return self.session is not None and self.user is not None

AUTH = AuthState()

def supabase_sign_in(email: str, password: str):
    """
    Email/password sign-in. Returns (ok, err_message_or_None).
    """
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        AUTH.session = res.session
        AUTH.user = res.user
        return True, None
    except Exception as e:
        return False, str(e)

def supabase_sign_out():
    try:
        supabase.auth.sign_out()
    finally:
        AUTH.session = None
        AUTH.user = None


# ---------- Google Cloud setup ----------
# Set Google Cloud Project
os.environ['GOOGLE_CLOUD_PROJECT'] = 'perfect-entry-473503-j1'

# Google Cloud logging
try:
    from google.cloud import logging as cloud_logging
    CLOUD_LOGGING_AVAILABLE = True
    print("✅ Google Cloud logging imports successful")
except ImportError:
    CLOUD_LOGGING_AVAILABLE = False
    print("⚠️ Google Cloud logging not available")


class HealthDataManager:
    """Manages health data retrieval from Google Cloud"""

    def __init__(self):
        self.cloud_logging_client = None
        self.logger_name = 'straightup-adk-production'

        if CLOUD_LOGGING_AVAILABLE:
            try:
                self.cloud_logging_client = cloud_logging.Client(project='perfect-entry-473503-j1')
                print("🌐 Google Cloud logging client initialized")
            except Exception as e:
                print(f"⚠️ Cloud logging initialization failed: {e}")

    def get_recent_health_data(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch recent health data from Google Cloud Logging"""
        if not self.cloud_logging_client:
            return self._generate_sample_data()

        try:
            # Calculate time range
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)

            # Query Google Cloud Logging
            filter_str = f'''
                logName="projects/perfect-entry-473503-j1/logs/{self.logger_name}"
                AND timestamp >= "{start_time.isoformat()}Z"
                AND timestamp <= "{end_time.isoformat()}Z"
                AND jsonPayload.source="adk_production_system"
            '''

            entries = list(self.cloud_logging_client.list_entries(
                filter_=filter_str,
                order_by=cloud_logging.DESCENDING,
                max_results=limit
            ))

            health_data = []
            for entry in entries:
                if hasattr(entry, 'payload') and isinstance(entry.payload, dict):
                    data_point = {
                        'timestamp': entry.timestamp.isoformat() if entry.timestamp else datetime.utcnow().isoformat(),
                        'focus_score': entry.payload.get('focus_score', 0.5),
                        'posture_score': entry.payload.get('posture_score', 0.5),
                        'phone_usage_seconds': entry.payload.get('phone_usage_seconds', 0.0),
                        'noise_level': entry.payload.get('noise_level', 0.3),
                        'recommendations': entry.payload.get('recommendations', []),
                        'cycle': entry.payload.get('cycle', 0),
                        'agent_status': entry.payload.get('agent_status', 'unknown')
                    }
                    health_data.append(data_point)

            print(f"📊 Retrieved {len(health_data)} health data points from Google Cloud")
            return health_data

        except Exception as e:
            print(f"⚠️ Error fetching from Google Cloud: {e}")
            return self._generate_sample_data()

    def get_health_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get aggregated health summary statistics"""
        data = self.get_recent_health_data(hours)

        if not data:
            return {
                'status': 'no_data',
                'message': 'No health data available'
            }

        # Calculate averages and trends
        total_points = len(data)
        avg_focus = sum(d['focus_score'] for d in data) / total_points
        avg_posture = sum(d['posture_score'] for d in data) / total_points
        total_phone_time = sum(d['phone_usage_seconds'] for d in data)
        avg_noise = sum(d['noise_level'] for d in data) / total_points

        # Get recent vs older data for trends
        recent_data = data[:total_points//3] if total_points > 6 else data
        older_data = data[total_points//3:] if total_points > 6 else data

        recent_focus = sum(d['focus_score'] for d in recent_data) / len(recent_data) if recent_data else avg_focus
        older_focus = sum(d['focus_score'] for d in older_data) / len(older_data) if older_data else avg_focus

        focus_trend = 'improving' if recent_focus > older_focus else 'declining' if recent_focus < older_focus else 'stable'

        # Collect all recommendations
        all_recommendations = []
        for entry in data:
            all_recommendations.extend(entry.get('recommendations', []))

        # Count recommendation frequency
        rec_counts = {}
        for rec in all_recommendations:
            rec_counts[rec] = rec_counts.get(rec, 0) + 1

        top_recommendations = sorted(rec_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        # Generate live data format from most recent entry
        live_data = self._generate_live_data_from_recent(data)

        return {
            'status': 'success',
            'data_points': total_points,
            'time_range_hours': hours,
            'averages': {
                'focus_score': round(avg_focus, 3),
                'posture_score': round(avg_posture, 3),
                'noise_level': round(avg_noise, 3)
            },
            'totals': {
                'phone_usage_seconds': round(total_phone_time, 1),
                'phone_usage_minutes': round(total_phone_time / 60, 1)
            },
            'trends': {
                'focus_trend': focus_trend,
                'recent_focus': round(recent_focus, 3),
                'older_focus': round(older_focus, 3)
            },
            'top_recommendations': [{'text': rec, 'count': count} for rec, count in top_recommendations],
            'health_grade': self._calculate_health_grade(avg_focus, avg_posture, total_phone_time, avg_noise),
            'last_updated': data[0]['timestamp'] if data else datetime.utcnow().isoformat(),
            'live_data': live_data,
            'metrics': {
                'distraction_level': round((1 - avg_focus) * 100, 1),
                'focus_score': round(avg_focus * 100, 1),
                'posture_score': round(avg_posture * 100, 1)
            }
        }

    def _generate_live_data_from_recent(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate live data format from recent entries"""
        if not data:
            return {
                'postureScore': {'value': '75%', 'status': 'good'},
                'phoneUsage': {'value': '2.3 min', 'status': 'ok'},
                'noiseLevel': {'value': '28%', 'status': 'good'},
                'focusScore': {'value': '64%', 'status': 'warn'}
            }

        # Use most recent 5 entries for live data
        recent_entries = data[:5]

        avg_posture = sum(d['posture_score'] for d in recent_entries) / len(recent_entries)
        avg_focus = sum(d['focus_score'] for d in recent_entries) / len(recent_entries)
        avg_noise = sum(d['noise_level'] for d in recent_entries) / len(recent_entries)
        total_phone = sum(d['phone_usage_seconds'] for d in recent_entries)

        return {
            'postureScore': {
                'value': f"{int(avg_posture * 100)}%",
                'status': 'good' if avg_posture > 0.7 else 'warn' if avg_posture > 0.4 else 'bad'
            },
            'focusScore': {
                'value': f"{int(avg_focus * 100)}%",
                'status': 'good' if avg_focus > 0.7 else 'warn' if avg_focus > 0.4 else 'bad'
            },
            'noiseLevel': {
                'value': f"{int(avg_noise * 100)}%",
                'status': 'good' if avg_noise < 0.3 else 'warn' if avg_noise < 0.6 else 'bad'
            },
            'phoneUsage': {
                'value': f"{total_phone / 60:.1f} min",
                'status': 'good' if total_phone < 300 else 'warn' if total_phone < 900 else 'bad'
            }
        }

    def _calculate_health_grade(self, focus: float, posture: float, phone_time: float, noise: float) -> str:
        """Calculate overall health grade"""
        focus_score = focus * 100
        posture_score = posture * 100
        phone_penalty = min(phone_time / 300 * 20, 20)
        noise_penalty = noise * 30

        overall = (focus_score + posture_score - phone_penalty - noise_penalty) / 2

        if overall >= 85:
            return 'A'
        elif overall >= 75:
            return 'B'
        elif overall >= 65:
            return 'C'
        elif overall >= 55:
            return 'D'
        else:
            return 'F'

    def _generate_sample_data(self) -> List[Dict[str, Any]]:
        """Generate sample data for demo purposes"""
        import random

        sample_data = []
        base_time = datetime.utcnow()

        for i in range(20):
            timestamp = base_time - timedelta(minutes=i * 5)
            sample_data.append({
                'timestamp': timestamp.isoformat(),
                'focus_score': round(random.uniform(0.4, 0.9), 3),
                'posture_score': round(random.uniform(0.3, 0.9), 3),
                'phone_usage_seconds': round(random.uniform(0, 45), 1),
                'noise_level': round(random.uniform(0.1, 0.6), 3),
                'recommendations': random.choice([
                    ['🎯 Focus on alignment', '✅ Good posture'],
                    ['🔴 Neck flexion critical - Raise monitor', '🟡 Minor shoulder imbalance'],
                    ['📱 Brief phone check', '🌟 Excellent posture!'],
                    []
                ]),
                'cycle': 100 - i,
                'agent_status': 'operational'
            })

        return sample_data


class ModernTkinterApp:
    """Modern desktop app using pure Tkinter with web UI styling"""

    #---------------------------------------------------------------------

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("iMPOSTURE — Desktop Dashboard")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)

        # Color scheme matching web UI
        self.colors = {
            'bg': '#0B0F17',
            'card': '#111827',
            'muted': '#9AA4B2',
            'border': '#273047',
            'ink': '#ffffff',
            'accent': '#4F46E5',
            'accent2': '#22C55E',
            'danger': '#ef4444',
            'warn': '#f59e0b',
            'panel': '#0F1626'
        }

        # Setup styles
        self.setup_styles()

        # Initialize data manager
        self.data_manager = HealthDataManager()

        # App state
        self.session_running = False
        self.session_paused = False
        self.session_start_time = None
        self.session_elapsed = 0
        self.timer_id = None
        self.auto_refresh = True
        self.current_data = None

        # Break scheduling state (defaults)
        self.break_freq_minutes: int = 5
        self.break_len_minutes: int = 5
        self.in_break: bool = False
        self.next_break_time: Optional[datetime] = None
        self.break_end_time: Optional[datetime] = None

        # Start on the auth screen (login / sign up)
        self.show_auth_gate()

    #---------------------------------------------------------------------

    def run(self):
        """Run the desktop application"""
        print("🚀 Starting Modern StraightUp Desktop App...")
        print("🎯 Project: perfect-entry-473503-j1")
        print("📊 Modern UI matching web design (Pure Tkinter)")
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("\n🛑 Desktop app closed by user")
        except Exception as e:
            print(f"❌ Desktop app error: {e}")

    #---------------------------------------------------------------------

    def setup_styles(self):
        """Setup custom styles and colors"""
        # Configure root
        self.root.configure(bg=self.colors['bg'])

        # Setup fonts
        self.fonts = {
            'title': font.Font(family="Segoe UI", size=20, weight="bold"),
            'subtitle': font.Font(family="Segoe UI", size=18, weight="bold"),
            'body': font.Font(family="Segoe UI", size=12),
            'small': font.Font(family="Segoe UI", size=10),
            'timer': font.Font(family="Segoe UI", size=48, weight="bold"),
            'large': font.Font(family="Segoe UI", size=36, weight="bold")
        }

        # Configure ttk styles
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Custom button style
        self.style.configure(
            'Modern.TButton',
            background=self.colors['card'],
            foreground=self.colors['ink'],
            borderwidth=1,
            relief='solid',
            bordercolor=self.colors['border'],
            focuscolor='none'
        )

        self.style.map(
            'Modern.TButton',
            background=[('active', self.colors['panel'])],
            bordercolor=[('active', self.colors['accent'])]
        )

        # Danger button style
        self.style.configure(
            'Danger.TButton',
            background=self.colors['danger'],
            foreground='white',
            borderwidth=0,
            relief='flat',
            focuscolor='none'
        )

        self.style.map(
            'Danger.TButton',
            background=[('active', '#dc2626')]
        )

    #---------------------------------------------------------------------
    # AUTH GATE (LOGIN / SIGN-UP)
    #---------------------------------------------------------------------

    def show_auth_gate(self):
        """Render a full-screen auth screen with Login / Sign up tabs. On success -> dashboard."""
        # Root background
        self.root.configure(bg=self.colors['bg'])

        # Top-level container that fills the window
        self.auth_frame = tk.Frame(self.root, bg=self.colors['bg'])
        self.auth_frame.pack(fill="both", expand=True, padx=40, pady=40)

        # Card
        card = tk.Frame(
            self.auth_frame,
            bg=self.colors['card'],
            relief="solid",
            bd=1,
            highlightbackground=self.colors['border']
        )
        card.place(relx=0.5, rely=0.5, anchor="center", width=520, height=460)

        header = tk.Label(
            card, text="iMPOSTURE — Sign in",
            font=self.fonts['title'],
            fg=self.colors['ink'], bg=self.colors['card']
        )
        header.pack(pady=(18, 4))

        sub = tk.Label(
            card, text="Log in to continue to your dashboard",
            font=self.fonts['body'], fg=self.colors['muted'], bg=self.colors['card']
        )
        sub.pack(pady=(0, 10))

        # Notebook with Login / Sign up
        nb = ttk.Notebook(card)
        nb.pack(fill="both", expand=True, padx=18, pady=12)

        # -------- Login tab --------
        login_tab = tk.Frame(nb, bg=self.colors['card'])
        nb.add(login_tab, text="Login")

        tk.Label(login_tab, text="Email", font=self.fonts['body'],
                 fg=self.colors['ink'], bg=self.colors['card']).pack(anchor="w", padx=8, pady=(8,2))
        login_email = tk.StringVar()
        tk.Entry(login_tab, textvariable=login_email).pack(fill="x", padx=8, pady=(0,8))

        tk.Label(login_tab, text="Password", font=self.fonts['body'],
                 fg=self.colors['ink'], bg=self.colors['card']).pack(anchor="w", padx=8, pady=(8,2))
        login_pwd = tk.StringVar()
        tk.Entry(login_tab, textvariable=login_pwd, show="•").pack(fill="x", padx=8, pady=(0,12))

        login_status = tk.Label(login_tab, text="", font=self.fonts['small'],
                                fg=self.colors['warn'], bg=self.colors['card'])
        login_status.pack(anchor="w", padx=8)

        def _do_login():
            email = login_email.get().strip()
            pwd = login_pwd.get()
            if not email or not pwd:
                login_status.configure(text="Please enter email and password", fg=self.colors['warn'])
                return
            ok, err = supabase_sign_in(email, pwd)
            if ok and AUTH.is_authenticated():
                login_status.configure(text="Signed in ✅", fg=self.colors['accent2'])
                self.enter_dashboard()  # proceed
            else:
                login_status.configure(text=f"Error: {err}", fg=self.colors['danger'])

        tk.Button(
            login_tab, text="Sign in", bg=self.colors['accent'], fg="black",
            relief="flat", command=_do_login
        ).pack(pady=8)

        # -------- Sign up tab --------
        signup_tab = tk.Frame(nb, bg=self.colors['card'])
        nb.add(signup_tab, text="Sign up")

        tk.Label(signup_tab, text="Email", font=self.fonts['body'],
                 fg=self.colors['ink'], bg=self.colors['card']).pack(anchor="w", padx=8, pady=(8,2))
        su_email = tk.StringVar()
        tk.Entry(signup_tab, textvariable=su_email).pack(fill="x", padx=8, pady=(0,8))

        tk.Label(signup_tab, text="Password", font=self.fonts['body'],
                 fg=self.colors['ink'], bg=self.colors['card']).pack(anchor="w", padx=8, pady=(8,2))
        su_pwd = tk.StringVar()
        tk.Entry(signup_tab, textvariable=su_pwd, show="•").pack(fill="x", padx=8, pady=(0,8))

        tk.Label(signup_tab, text="Confirm password", font=self.fonts['body'],
                 fg=self.colors['ink'], bg=self.colors['card']).pack(anchor="w", padx=8, pady=(8,2))
        su_pwd2 = tk.StringVar()
        tk.Entry(signup_tab, textvariable=su_pwd2, show="•").pack(fill="x", padx=8, pady=(0,8))

        signup_status = tk.Label(signup_tab, text="", font=self.fonts['small'],
                                 fg=self.colors['warn'], bg=self.colors['card'])
        signup_status.pack(anchor="w", padx=8)

        def _do_signup():
            email = su_email.get().strip()
            pwd1 = su_pwd.get()
            pwd2 = su_pwd2.get()
            if not email or not pwd1:
                signup_status.configure(text="Please enter email and password", fg=self.colors['warn'])
                return
            if pwd1 != pwd2:
                signup_status.configure(text="Passwords do not match", fg=self.colors['danger'])
                return
            try:
                res = supabase.auth.sign_up({"email": email, "password": pwd1})
                # If your Supabase project requires email confirmation, res.session may be None.
                if getattr(res, "session", None):
                    # Signed in right away
                    AUTH.session = res.session
                    AUTH.user = res.user
                    self.enter_dashboard()
                else:
                    # Ask user to confirm email, then sign in
                    signup_status.configure(
                        text="Check your email to confirm your account, then return to Login tab.",
                        fg=self.colors['accent2']
                    )
            except Exception as e:
                signup_status.configure(text=f"Sign-up error: {e}", fg=self.colors['danger'])

        tk.Button(
            signup_tab, text="Create account", bg=self.colors['accent'], fg="black",
            relief="flat", command=_do_signup
        ).pack(pady=8)

    def enter_dashboard(self):
        """Tear down auth screen and build the main dashboard."""
        # Remove auth UI
        if hasattr(self, "auth_frame") and self.auth_frame.winfo_exists():
            self.auth_frame.destroy()

        # Optional: personalize window title
        if AUTH.user and getattr(AUTH.user, "email", None):
            self.root.title(f"iMPOSTURE — {AUTH.user.email}")

        # Build the real app now
        self.setup_ui()
        self.setup_refresh_timer()
        self.refresh_data()

    def require_login(self):
        """Modal login dialog (gate a specific action)."""
        if AUTH.is_authenticated():
            return True

        win = tk.Toplevel(self.root)
        win.title("Sign in")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)
        win.configure(bg=self.colors['card'], padx=16, pady=16)

        tk.Label(
            win,
            text="Email",
            bg=self.colors['card'],
            fg=self.colors['ink'],
            font=self.fonts['body']
        ).grid(row=0, column=0, sticky="w")

        email_var = tk.StringVar()
        tk.Entry(win, textvariable=email_var).grid(row=1, column=0, sticky="we", pady=(0,8))

        tk.Label(
            win,
            text="Password",
            bg=self.colors['card'],
            fg=self.colors['ink'],
            font=self.fonts['body']
        ).grid(row=2, column=0, sticky="w")

        pwd_var = tk.StringVar()
        tk.Entry(win, textvariable=pwd_var, show="•").grid(row=3, column=0, sticky="we", pady=(0,12))

        status = tk.Label(
            win,
            text="",
            bg=self.colors['card'],
            fg=self.colors['warn'],
            font=self.fonts['small']
        )
        status.grid(row=4, column=0, sticky="w")

        btns = tk.Frame(win, bg=self.colors['card'])
        btns.grid(row=5, column=0, sticky="e", pady=(12,0))

        def _do_login():
            ok, err = supabase_sign_in(email_var.get().strip(), pwd_var.get())
            if ok:
                status.configure(text="Signed in ✅", fg=self.colors['accent2'])
                win.destroy()
            else:
                status.configure(text=f"Error: {err}", fg=self.colors['danger'])

        tk.Button(btns, text="Cancel", command=win.destroy).pack(side="left", padx=(0,8))
        tk.Button(
            btns,
            text="Sign in",
            bg=self.colors['accent'],
            fg="black",
            relief="flat",
            command=_do_login
        ).pack(side="left")

        # Center window & block
        win.update_idletasks()
        win.geometry(f"+{self.root.winfo_rootx()+60}+{self.root.winfo_rooty()+80}")
        self.root.wait_window(win)

        return AUTH.is_authenticated()

    #---------------------------------------------------------------------
    # DASHBOARD UI
    #---------------------------------------------------------------------

    def setup_ui(self):
        """Setup the user interface"""
        # Main container with padding
        self.main_frame = tk.Frame(self.root, bg=self.colors['bg'])
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Setup components
        self.setup_header()
        self.setup_badges()
        self.setup_main_content()

    def setup_header(self):
        """Setup header with logo and controls"""
        header_frame = tk.Frame(self.main_frame, bg=self.colors['bg'])
        header_frame.pack(fill="x", pady=(0, 16))

        # Brand section
        brand_frame = tk.Frame(header_frame, bg=self.colors['bg'])
        brand_frame.pack(side="left", fill="y")

        # Logo
        logo_frame = tk.Frame(
            brand_frame,
            width=36, height=36,
            bg=self.colors['accent'],
            relief='solid',
            bd=1
        )
        logo_frame.pack(side="left", padx=(0, 12))
        logo_frame.pack_propagate(False)

        logo_label = tk.Label(
            logo_frame,
            text="⬆",
            font=self.fonts['subtitle'],
            fg="white",
            bg=self.colors['accent']
        )
        logo_label.pack(expand=True)

        # Title
        title_label = tk.Label(
            brand_frame,
            text="iMPOSTURE",
            font=self.fonts['title'],
            fg=self.colors['ink'],
            bg=self.colors['bg']
        )
        title_label.pack(side="left")

        # Control buttons
        controls_frame = tk.Frame(header_frame, bg=self.colors['bg'])
        controls_frame.pack(side="right")

        # Status indicator
        self.status_label = tk.Label(
            controls_frame,
            text="🔴 Connecting...",
            font=self.fonts['small'],
            fg=self.colors['muted'],
            bg=self.colors['bg']
        )
        self.status_label.pack(side="right", padx=(0, 20))

        # Settings button
        settings_btn = tk.Button(
            controls_frame,
            text="Settings",
            font=self.fonts['body'],
            fg="black",
            bg=self.colors['card'],
            relief='solid',
            bd=1,
            highlightbackground=self.colors['border'],
            activebackground=self.colors['panel'],
            activeforeground=self.colors['ink'],
            command=self.show_settings
        )
        settings_btn.pack(side="right", padx=5)

        # Refresh button
        refresh_btn = tk.Button(
            controls_frame,
            text="Refresh",
            font=self.fonts['body'],
            fg="black",
            bg=self.colors['danger'],
            relief='flat',
            bd=0,
            activebackground="#dc2626",
            activeforeground="white",
            command=self.refresh_data
        )
        refresh_btn.pack(side="right", padx=5)

    def setup_badges(self):
        """Setup incentive badges"""
        badges_frame = tk.Frame(self.main_frame, bg=self.colors['bg'])
        badges_frame.pack(fill="x", pady=(0, 16))

        # Level badge
        level_badge = self.create_badge(
            badges_frame,
            "🏅",
            "Lv. 1 — Starter",
            "Next: 80 min total"
        )
        level_badge.pack(side="left", fill="x", expand=True, padx=(0, 6))

        # Today badge
        self.today_badge = self.create_badge(
            badges_frame,
            "⏱️",
            "0 min today",
            "Consistency beats intensity"
        )
        self.today_badge.pack(side="left", fill="x", expand=True, padx=6)

        # Goal badge
        goal_badge = self.create_badge(
            badges_frame,
            "🎯",
            "Daily goal: 45 min",
            "Adjust in setup"
        )
        goal_badge.pack(side="left", fill="x", expand=True, padx=(6, 0))

    def create_badge(self, parent, icon, title, subtitle):
        """Create a badge with icon and text"""
        badge_frame = tk.Frame(
            parent,
            bg=self.colors['card'],
            relief='solid',
            bd=1,
            highlightbackground=self.colors['border']
        )

        content_frame = tk.Frame(badge_frame, bg=self.colors['card'])
        content_frame.pack(fill="both", expand=True, padx=14, pady=14)

        # Icon
        icon_frame = tk.Frame(
            content_frame,
            width=36, height=36,
            bg=self.colors['accent'],
            relief='solid',
            bd=1
        )
        icon_frame.pack(side="left", padx=(0, 10))
        icon_frame.pack_propagate(False)

        icon_label = tk.Label(
            icon_frame,
            text=icon,
            font=self.fonts['body'],
            bg=self.colors['accent'],
            fg="white"
        )
        icon_label.pack(expand=True)

        # Text content
        text_frame = tk.Frame(content_frame, bg=self.colors['card'])
        text_frame.pack(side="left", fill="both", expand=True)

        title_label = tk.Label(
            text_frame,
            text=title,
            font=font.Font(family="Segoe UI", size=11, weight="bold"),
            fg=self.colors['ink'],
            bg=self.colors['card'],
            anchor="w"
        )
        title_label.pack(fill="x")

        subtitle_label = tk.Label(
            text_frame,
            text=subtitle,
            font=self.fonts['small'],
            fg=self.colors['muted'],
            bg=self.colors['card'],
            anchor="w"
        )
        subtitle_label.pack(fill="x")

        # Store reference to title label for updates
        badge_frame.title_label = title_label

        return badge_frame

    def setup_main_content(self):
        """Setup main two-column content area"""
        content_frame = tk.Frame(self.main_frame, bg=self.colors['bg'])
        content_frame.pack(fill="both", expand=True)

        # Session card (left column)
        self.setup_session_card(content_frame)

        # Wellness card (right column)
        self.setup_wellness_card(content_frame)

    def setup_session_card(self, parent):
        """Setup session control card"""
        session_card = tk.Frame(
            parent,
            bg=self.colors['card'],
            relief='solid',
            bd=1,
            highlightbackground=self.colors['border']
        )
        session_card.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # Card content
        card_content = tk.Frame(session_card, bg=self.colors['card'])
        card_content.pack(fill="both", expand=True, padx=18, pady=18)

        # Welcome message
        self.welcome_label = tk.Label(
            card_content,
            text="Welcome back",
            font=self.fonts['title'],
            fg=self.colors['ink'],
            bg=self.colors['card'],
            anchor="w"
        )
        self.welcome_label.pack(fill="x", pady=(0, 6))

        # Session title
        session_title = tk.Label(
            card_content,
            text="Session",
            font=self.fonts['subtitle'],
            fg=self.colors['ink'],
            bg=self.colors['card'],
            anchor="w"
        )
        session_title.pack(fill="x", pady=(0, 10))

        # Session subtitle
        self.session_subtitle = tk.Label(
            card_content,
            text="Configure your session, then start. We'll time it and track progress.",
            font=self.fonts['body'],
            fg=self.colors['muted'],
            bg=self.colors['card'],
            anchor="w",
            wraplength=400,
            justify="left"
        )
        self.session_subtitle.pack(fill="x", pady=(0, 8))

        # Timer display
        timer_frame = tk.Frame(
            card_content,
            bg=self.colors['panel'],
            relief='solid',
            bd=1,
            highlightbackground="#2a3350"
        )
        timer_frame.pack(fill="x", pady=(0, 10))

        self.timer_label = tk.Label(
            timer_frame,
            text="00:00",
            font=self.fonts['timer'],
            fg=self.colors['ink'],
            bg=self.colors['panel']
        )
        self.timer_label.pack(pady=18)

        # Control buttons
        controls_frame = tk.Frame(card_content, bg=self.colors['card'])
        controls_frame.pack(fill="x", pady=(0, 10))

        self.setup_btn = tk.Button(
            controls_frame,
            text="Open session setup",
            font=self.fonts['body'],
            fg='black',
            bg=self.colors['card'],
            relief='solid',
            bd=1,
            highlightbackground=self.colors['border'],
            activebackground=self.colors['panel'],
            activeforeground=self.colors['ink'],
            command=self.open_session_setup
        )
        self.setup_btn.pack(side="left", padx=(0, 5))

        self.pause_btn = tk.Button(
            controls_frame,
            text="Pause",
            font=self.fonts['body'],
            fg="black",
            disabledforeground="black",
            bg=self.colors['panel'],
            relief='solid',
            bd=1,
            highlightbackground=self.colors['border'],
            state="disabled",
            command=self.pause_session
        )
        self.pause_btn.pack(side="left", padx=5)

        self.stop_btn = tk.Button(
            controls_frame,
            text="Stop & Save",
            disabledforeground="black",
            font=self.fonts['body'],
            fg="black",
            bg=self.colors['panel'],
            relief='solid',
            bd=1,
            highlightbackground=self.colors['border'],
            state="disabled",
            command=self.stop_session
        )
        self.stop_btn.pack(side="left", padx=5)

        # Status pill
        status_frame = tk.Frame(
            controls_frame,
            bg=self.colors['panel'],
            relief='solid',
            bd=1,
            highlightbackground=self.colors['border']
        )
        status_frame.pack(side="right")

        status_content = tk.Frame(status_frame, bg=self.colors['panel'])
        status_content.pack(padx=14, pady=10)

        # Status dot
        self.status_dot = tk.Label(
            status_content,
            text="●",
            font=self.fonts['body'],
            fg=self.colors['accent2'],
            bg=self.colors['panel']
        )
        self.status_dot.pack(side="left", padx=(0, 6))

        self.session_status_label = tk.Label(
            status_content,
            text="Idle",
            font=self.fonts['body'],
            fg=self.colors['ink'],
            bg=self.colors['panel']
        )
        self.session_status_label.pack(side="left")

        # Live summary section
        self.setup_live_summary(card_content)

    def setup_live_summary(self, parent):
        """Setup live wellness summary"""
        summary_frame = tk.Frame(
            parent,
            bg=self.colors['card'],
            relief='solid',
            bd=1,
            highlightbackground=self.colors['border']
        )
        summary_frame.pack(fill="x", pady=(18, 0))

        # Header
        header_frame = tk.Frame(summary_frame, bg=self.colors['card'])
        header_frame.pack(fill="x", padx=16, pady=(16, 10))

        summary_title = tk.Label(
            header_frame,
            text="Live wellness",
            font=font.Font(family="Segoe UI", size=12, weight="bold"),
            fg=self.colors['ink'],
            bg=self.colors['card']
        )
        summary_title.pack(side="left")

        self.live_dot = tk.Label(
            header_frame,
            text="●",
            font=self.fonts['small'],
            fg=self.colors['muted'],
            bg=self.colors['card']
        )
        self.live_dot.pack(side="right")

        # Summary content
        self.live_summary_frame = tk.Frame(summary_frame, bg=self.colors['card'])
        self.live_summary_frame.pack(fill="x", padx=16, pady=(0, 16))

        # Initial loading chip
        loading_chip = self.create_chip(self.live_summary_frame, "Loading live summary…", "muted")
        loading_chip.pack(side="left")

    def create_chip(self, parent, text, status="muted", icon="•"):
        """Create a status chip"""
        colors = {
            'good': {'fg': self.colors['accent2'], 'border': self.colors['accent2']},
            'warn': {'fg': self.colors['warn'], 'border': self.colors['warn']},
            'bad': {'fg': self.colors['danger'], 'border': self.colors['danger']},
            'muted': {'fg': self.colors['muted'], 'border': self.colors['border']}
        }

        chip_colors = colors.get(status, colors['muted'])

        chip = tk.Frame(
            parent,
            bg=self.colors['card'],
            relief='solid',
            bd=1,
            highlightbackground=chip_colors['border']
        )

        content_frame = tk.Frame(chip, bg=self.colors['card'])
        content_frame.pack(padx=14, pady=8)

        # Icon
        icon_label = tk.Label(
            content_frame,
            text=icon,
            font=self.fonts['body'],
            fg=chip_colors['fg'],
            bg=self.colors['card']
        )
        icon_label.pack(side="left", padx=(0, 8))

        # Text
        text_label = tk.Label(
            content_frame,
            text=text,
            font=font.Font(family="Segoe UI", size=11, weight="bold"),
            fg=chip_colors['fg'],
            bg=self.colors['card']
        )
        text_label.pack(side="left")

        return chip

    def setup_wellness_card(self, parent):
        """Setup wellness report card"""
        wellness_card = tk.Frame(
            parent,
            bg=self.colors['card'],
            relief='solid',
            bd=1,
            highlightbackground=self.colors['border']
        )
        wellness_card.pack(side="right", fill="both", expand=True, padx=(8, 0))

        # Card content
        card_content = tk.Frame(wellness_card, bg=self.colors['card'])
        card_content.pack(fill="both", expand=True, padx=18, pady=18)

        # Title
        title_label = tk.Label(
            card_content,
            text="Wellness report",
            font=self.fonts['subtitle'],
            fg=self.colors['ink'],
            bg=self.colors['card'],
            anchor="w"
        )
        title_label.pack(fill="x", pady=(0, 10))

        # Subtitle
        subtitle_label = tk.Label(
            card_content,
            text="Snapshot of posture, focus, distractions, and break habits.",
            font=self.fonts['body'],
            fg=self.colors['muted'],
            bg=self.colors['card'],
            anchor="w",
            wraplength=400,
            justify="left"
        )
        subtitle_label.pack(fill="x", pady=(0, 8))

        # Metrics grid
        metrics_frame = tk.Frame(card_content, bg=self.colors['card'])
        metrics_frame.pack(fill="both", expand=True)

        # Configure grid weights
        metrics_frame.grid_columnconfigure(0, weight=1)
        metrics_frame.grid_columnconfigure(1, weight=1)
        metrics_frame.grid_rowconfigure(0, weight=1)
        metrics_frame.grid_rowconfigure(1, weight=1)

        # Create metric widgets
        self.distraction_metric = self.create_metric_widget(
            metrics_frame, "Distraction level", "Lower is better."
        )
        self.distraction_metric.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))

        self.focus_metric = self.create_metric_widget(
            metrics_frame, "Focus score", "Sustained work time."
        )
        self.focus_metric.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 6))

        self.posture_metric = self.create_metric_widget(
            metrics_frame, "Posture score", "Neck and shoulder alignment."
        )
        self.posture_metric.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=(6, 0))

        # Empty space for symmetry
        empty_frame = tk.Frame(metrics_frame, bg=self.colors['card'])
        empty_frame.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=(6, 0))

    def create_metric_widget(self, parent, title, hint):
        """Create a metric display widget with progress bar"""
        metric_frame = tk.Frame(
            parent,
            bg=self.colors['panel'],
            relief='solid',
            bd=1,
            highlightbackground=self.colors['border']
        )

        content_frame = tk.Frame(metric_frame, bg=self.colors['panel'])
        content_frame.pack(fill="both", expand=True, padx=14, pady=14)

        # Header with title and percentage
        header_frame = tk.Frame(content_frame, bg=self.colors['panel'])
        header_frame.pack(fill="x", pady=(0, 6))

        title_label = tk.Label(
            header_frame,
            text=title,
            font=font.Font(family="Segoe UI", size=11, weight="bold"),
            fg=self.colors['ink'],
            bg=self.colors['panel'],
            anchor="w"
        )
        title_label.pack(side="left")

        pct_label = tk.Label(
            header_frame,
            text="—",
            font=self.fonts['body'],
            fg=self.colors['muted'],
            bg=self.colors['panel']
        )
        pct_label.pack(side="right")

        # Progress bar container
        progress_bg = tk.Frame(
            content_frame,
            height=12,
            bg="#0c1220",
            relief='solid',
            bd=1,
            highlightbackground="#223055"
        )
        progress_bg.pack(fill="x", pady=(0, 6))
        progress_bg.pack_propagate(False)

        # Progress bar (simulated with colored frame)
        progress_bar = tk.Frame(
            progress_bg,
            height=10,
            bg=self.colors['accent2']
        )
        progress_bar.pack(side="left", padx=1, pady=1)

        # Hint
        hint_label = tk.Label(
            content_frame,
            text=hint,
            font=self.fonts['small'],
            fg=self.colors['muted'],
            bg=self.colors['panel'],
            anchor="w"
        )
        hint_label.pack(fill="x")

        # Store references for updates
        metric_frame.pct_label = pct_label
        metric_frame.progress_bar = progress_bar
        metric_frame.progress_bg = progress_bg

        return metric_frame

    def update_progress_bar(self, metric_widget, percentage):
        """Update progress bar width"""
        bg_width = metric_widget.progress_bg.winfo_width()
        if bg_width > 1:  # Only update if widget is properly sized
            bar_width = max(1, int((bg_width - 2) * percentage / 100))
            metric_widget.progress_bar.configure(width=bar_width)

    def setup_refresh_timer(self):
        """Setup auto-refresh timer"""
        if self.auto_refresh:
            self.root.after(5000, self.auto_refresh_data)  # Refresh every 5 seconds

    def auto_refresh_data(self):
        """Auto-refresh data if enabled"""
        if self.auto_refresh:
            self.refresh_data()
            self.setup_refresh_timer()

    def refresh_data(self):
        """Refresh health data from backend"""
        def fetch_data():
            try:
                self.current_data = self.data_manager.get_health_summary()
                self.root.after(0, self.update_ui)
            except Exception as e:
                self.root.after(0, lambda: self.show_error(f"Failed to fetch data: {e}"))

        # Run in background thread
        thread = threading.Thread(target=fetch_data, daemon=True)
        thread.start()

        # Update status
        self.status_label.configure(text="🔄 Refreshing...")

    def update_ui(self):
        """Update UI with current data"""
        if not self.current_data or self.current_data.get('status') != 'success':
            self.status_label.configure(text="🔴 No Data Available")
            return

        data = self.current_data

        # Update status
        self.status_label.configure(text="🟢 System Active")

        # Update metrics
        metrics = data.get('metrics', {})

        # Distraction level (inverted for display)
        dist_pct = metrics.get('distraction_level', 28)
        display_dist = 100 - dist_pct
        self.distraction_metric.pct_label.configure(text=f"{display_dist}%")
        self.root.after(100, lambda: self.update_progress_bar(self.distraction_metric, display_dist))

        # Focus score
        focus_pct = metrics.get('focus_score', 64)
        self.focus_metric.pct_label.configure(text=f"{focus_pct}%")
        self.root.after(100, lambda: self.update_progress_bar(self.focus_metric, focus_pct))

        # Posture score
        posture_pct = metrics.get('posture_score', 75)
        self.posture_metric.pct_label.configure(text=f"{posture_pct}%")
        self.root.after(100, lambda: self.update_progress_bar(self.posture_metric, posture_pct))

        # Update live summary
        self.update_live_summary(data.get('live_data', {}))

    def update_live_summary(self, live_data):
        """Update live wellness summary chips"""
        # Clear existing chips
        for widget in self.live_summary_frame.winfo_children():
            widget.destroy()

        if not live_data:
            loading_chip = self.create_chip(self.live_summary_frame, "No live data available", "muted")
            loading_chip.pack(side="left")
            return

        # Create chips for each metric
        chip_count = 0
        max_chips = 3  # Limit to prevent overflow

        for key, value in live_data.items():
            if chip_count >= max_chips:
                break

            # Extract status and value
            if isinstance(value, dict):
                status = value.get('status', 'muted')
                display_value = value.get('value', '—')
            else:
                status = 'muted'
                display_value = str(value)

            # Create friendly names and icons
            display_name = self.get_friendly_name(key)
            icon = self.get_metric_icon(key)

            # Determine chip status
            chip_status = self.get_chip_status(status)

            chip_text = f"{display_name}: {display_value}"
            chip = self.create_chip(self.live_summary_frame, chip_text, chip_status, icon)
            chip.pack(side="left", padx=(0, 12))

            chip_count += 1

        # Update live dot color
        if chip_count > 0:
            self.live_dot.configure(fg=self.colors['accent2'])
        else:
            self.live_dot.configure(fg=self.colors['muted'])

    def get_friendly_name(self, key):
        """Convert API key to friendly display name"""
        names = {
            'postureScore': 'Posture',
            'phoneUsage': 'Phone',
            'noiseLevel': 'Noise',
            'focusScore': 'Focus'
        }
        return names.get(key, key)

    def get_metric_icon(self, key):
        """Get icon for metric"""
        icons = {
            'postureScore': '🧍‍♂️',
            'phoneUsage': '📱',
            'noiseLevel': '🔊',
            'focusScore': '🎯'
        }
        return icons.get(key, '•')

    def get_chip_status(self, status):
        """Convert API status to chip status"""
        status_map = {
            'good': 'good',
            'ok': 'good',
            'warn': 'warn',
            'warning': 'warn',
            'bad': 'bad',
            'error': 'bad'
        }
        return status_map.get(status.lower(), 'muted')

    #---------------------------------------------------------------------
    # SESSION SETUP + TIMER (with break scheduler)
    #---------------------------------------------------------------------

    def open_session_setup(self):
        """Open session setup dialog"""
        setup_window = tk.Toplevel(self.root)
        setup_window.title("Session Setup")
        setup_window.geometry("400x420")
        setup_window.configure(bg=self.colors['card'])
        setup_window.transient(self.root)
        setup_window.grab_set()

        # Setup window content
        content_frame = tk.Frame(setup_window, bg=self.colors['card'])
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        title_label = tk.Label(
            content_frame,
            text="Session setup",
            font=self.fonts['subtitle'],
            fg=self.colors['ink'],
            bg=self.colors['card']
        )
        title_label.pack(pady=(0, 20))

        # Settings
        settings_frame = tk.Frame(content_frame, bg=self.colors['card'])
        settings_frame.pack(fill="x", pady=(0, 20))

        # Break frequency
        break_freq_label = tk.Label(
            settings_frame,
            text="Break frequency (minutes)",
            font=self.fonts['body'],
            fg=self.colors['ink'],
            bg=self.colors['card'],
            anchor="w"
        )
        break_freq_label.pack(fill="x", pady=(0, 5))

        break_freq_var = tk.StringVar(value=str(self.break_freq_minutes))
        break_freq_combo = ttk.Combobox(
            settings_frame,
            textvariable=break_freq_var,
            values=["1", "5", "10", "15", "30"],
            state="readonly"
        )
        break_freq_combo.pack(fill="x", pady=(0, 10))

        # Break length
        break_len_label = tk.Label(
            settings_frame,
            text="Break length (minutes)",
            font=self.fonts['body'],
            fg=self.colors['ink'],
            bg=self.colors['card'],
            anchor="w"
        )
        break_len_label.pack(fill="x", pady=(0, 5))

        break_len_var = tk.StringVar(value=str(self.break_len_minutes))
        break_len_combo = ttk.Combobox(
            settings_frame,
            textvariable=break_len_var,
            values=["1", "5", "10", "15", "30"],
            state="readonly"
        )
        break_len_combo.pack(fill="x", pady=(0, 10))

        # Distraction tracking (placeholder)
        distraction_label = tk.Label(
            settings_frame,
            text="Distraction tracking",
            font=self.fonts['body'],
            fg=self.colors['ink'],
            bg=self.colors['card'],
            anchor="w"
        )
        distraction_label.pack(fill="x", pady=(0, 5))

        distraction_var = tk.BooleanVar(value=True)
        distraction_check = tk.Checkbutton(
            settings_frame,
            text="Alert for prolonged phone usage",
            variable=distraction_var,
            font=self.fonts['body'],
            fg=self.colors['ink'],
            bg=self.colors['card'],
            selectcolor=self.colors['panel'],
            activebackground=self.colors['card'],
            activeforeground=self.colors['ink']
        )
        distraction_check.pack(fill="x", pady=(0, 20))

        # Buttons
        button_frame = tk.Frame(content_frame, bg=self.colors['card'])
        button_frame.pack(fill="x")

        start_btn = tk.Button(
            button_frame,
            text="Start session",
            font=self.fonts['body'],
            fg="black",
            bg=self.colors['accent'],
            relief='flat',
            bd=0,
            activebackground="#3730a3",
            activeforeground="white",
            command=lambda: self.start_session(
                setup_window,
                int(break_freq_var.get()),
                int(break_len_var.get())
            )
        )
        start_btn.pack(side="left", padx=(0, 10))

        close_btn = tk.Button(
            button_frame,
            text="Close",
            font=self.fonts['body'],
            fg=self.colors['ink'],
            bg=self.colors['card'],
            relief='solid',
            bd=1,
            highlightbackground=self.colors['border'],
            activebackground=self.colors['panel'],
            activeforeground=self.colors['ink'],
            command=setup_window.destroy
        )
        close_btn.pack(side="left")

    def start_session(self, setup_window=None, break_freq_minutes: int = 5, break_len_minutes: int = 5):
        """Start a monitoring session"""
        if setup_window:
            setup_window.destroy()

        # Save the user’s choices
        self.break_freq_minutes = break_freq_minutes
        self.break_len_minutes = break_len_minutes

        # Reset break state and schedule the first break
        self.in_break = False
        self.next_break_time = datetime.now() + timedelta(minutes=self.break_freq_minutes)
        self.break_end_time = None

        self.session_running = True
        self.session_paused = False
        self.session_start_time = datetime.now()
        self.session_elapsed = 0

        # Update UI
        self.session_subtitle.configure(text="Timer active. We're tracking posture and focus.")
        self.pause_btn.configure(
            state="normal",
            fg=self.colors['ink'],
            bg=self.colors['card'],
            activebackground=self.colors['panel']
        )
        self.stop_btn.configure(
            state="normal",
            fg=self.colors['ink'],
            bg=self.colors['card'],
            activebackground=self.colors['panel']
        )
        self.session_status_label.configure(text="Running")
        self.status_dot.configure(fg=self.colors['danger'])

        # Start timer
        self.update_timer()

    def pause_session(self):
        """Pause/resume the session"""
        if not self.session_running:
            return

        self.session_paused = not self.session_paused

        if self.session_paused:
            self.session_elapsed += (datetime.now() - self.session_start_time).total_seconds()
            self.session_subtitle.configure(text="Resume when you're ready.")
            self.pause_btn.configure(text="Resume")
            self.session_status_label.configure(text="Paused")
            self.status_dot.configure(fg=self.colors['warn'])
        else:
            self.session_start_time = datetime.now()
            self.session_subtitle.configure(text="Timer active. We're tracking posture and focus.")
            self.pause_btn.configure(text="Pause")
            self.session_status_label.configure(text="Running")
            self.status_dot.configure(fg=self.colors['danger'])

        self.update_timer()

    def stop_session(self):
        """Stop and save the session"""
        if not self.session_running:
            return

        # Calculate total time
        if not self.session_paused:
            self.session_elapsed += (datetime.now() - self.session_start_time).total_seconds()

        # Reset session state
        self.session_running = False
        self.session_paused = False

        # Reset break scheduling state
        self.in_break = False
        self.next_break_time = None
        self.break_end_time = None

        # Update UI
        self.session_subtitle.configure(text="Configure your session, then start. We'll time it and track progress.")
        self.pause_btn.configure(
            state="disabled",
            text="Pause",
            fg="black",
            bg=self.colors['panel']
        )
        self.stop_btn.configure(
            state="disabled",
            fg=self.colors['muted'],
            bg=self.colors['panel']
        )
        self.session_status_label.configure(text="Idle")
        self.status_dot.configure(fg=self.colors['accent2'])
        self.timer_label.configure(text="00:00")

        # Show session summary
        minutes = int(self.session_elapsed // 60)
        seconds = int(self.session_elapsed % 60)

        if minutes > 0:
            messagebox.showinfo(
                "Session Complete",
                f"Session saved! Duration: {minutes}m {seconds}s\n\nGreat work on your focus session!"
            )

            # Update today badge
            self.today_badge.title_label.configure(text=f"{minutes} min today")
        else:
            messagebox.showwarning(
                "Session Too Short",
                "Session was too short to save (< 1 minute)."
            )

    def update_timer(self):
        """Update the session timer and manage breaks"""
        if self.session_running and not self.session_paused:
            current_elapsed = self.session_elapsed + (datetime.now() - self.session_start_time).total_seconds()
        else:
            current_elapsed = self.session_elapsed

        minutes = int(current_elapsed // 60)
        seconds = int(current_elapsed % 60)

        # Update timer label
        self.timer_label.configure(text=f"{minutes:02d}:{seconds:02d}")

        # --- Break scheduler ---
        if self.session_running and not self.session_paused:
            now = datetime.now()

            # If not in a break and it's time to start one
            if (not self.in_break) and self.next_break_time and now >= self.next_break_time:
                self.in_break = True
                self.break_end_time = now + timedelta(minutes=self.break_len_minutes)

            # If currently in a break and break time has ended
            if self.in_break and self.break_end_time and now >= self.break_end_time:
                self.in_break = False
                self.next_break_time = now + timedelta(minutes=self.break_freq_minutes)
                self.break_end_time = None

                # Show popup after break ends
                messagebox.showinfo(
                    "Break complete",
                    f"Your {self.break_len_minutes}-minute break just finished. Back to it!"
                )

        if self.session_running:
            self.timer_id = self.root.after(1000, self.update_timer)

    #---------------------------------------------------------------------

    def show_settings(self):
        """Show settings dialog"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("350x300")
        settings_window.configure(bg=self.colors['card'])
        settings_window.transient(self.root)
        settings_window.grab_set()

        content_frame = tk.Frame(settings_window, bg=self.colors['card'])
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)

        title_label = tk.Button(
            content_frame,
            text="Settings",
            font=self.fonts['subtitle'],
            fg="black",
            bg=self.colors['card']
        )
        title_label.pack(pady=(0, 20))

        # Auto refresh setting
        refresh_frame = tk.Frame(content_frame, bg=self.colors['card'])
        refresh_frame.pack(fill="x", pady=(0, 10))

        refresh_label = tk.Label(
            refresh_frame,
            text="Auto refresh data",
            font=self.fonts['body'],
            fg=self.colors['ink'],
            bg=self.colors['card']
        )
        refresh_label.pack(anchor="w")

        refresh_var = tk.BooleanVar(value=self.auto_refresh)
        refresh_check = tk.Checkbutton(
            refresh_frame,
            text="Enable automatic data refresh",
            variable=refresh_var,
            font=self.fonts['body'],
            fg=self.colors['ink'],
            bg=self.colors['card'],
            selectcolor=self.colors['panel'],
            activebackground=self.colors['card'],
            activeforeground=self.colors['ink'],
            command=lambda: setattr(self, 'auto_refresh', refresh_var.get())
        )
        refresh_check.pack(anchor="w", pady=(5, 0))

        # Project info
        info_frame = tk.Frame(
            content_frame,
            bg=self.colors['panel'],
            relief='solid',
            bd=1,
            highlightbackground=self.colors['border']
        )
        info_frame.pack(fill="x", pady=(20, 0))

        info_content = tk.Frame(info_frame, bg=self.colors['panel'])
        info_content.pack(fill="both", expand=True, padx=15, pady=15)

        info_text = f"""🎯 Project: perfect-entry-473503-j1
📊 Real-time ADK health monitoring
🌐 Google Cloud integration: {'✅' if CLOUD_LOGGING_AVAILABLE else '❌'}
🖥️ Desktop interface version"""

        info_label = tk.Label(
            info_content,
            text=info_text,
            font=self.fonts['small'],
            fg=self.colors['muted'],
            bg=self.colors['panel'],
            anchor="w",
            justify="left"
        )
        info_label.pack(fill="both", expand=True)

        # Close button
        close_btn = tk.Button(
            content_frame,
            text="Close",
            font=self.fonts['body'],
            fg="black",
            bg=self.colors['accent'],
            relief='flat',
            bd=0,
            activebackground="#3730a3",
            activeforeground="white",
            command=settings_window.destroy
        )
        close_btn.pack(pady=(20, 0))

    def show_error(self, message: str):
        """Show error message"""
        messagebox.showerror("Error", message)
        self.status_label.configure(text="🔴 Error")


# ---------- Main ----------
if __name__ == "__main__":
    print("🖥️ StraightUp Modern Desktop Dashboard - Pure Tkinter")
    print("=" * 60)
    print("🎯 Project: perfect-entry-473503-j1")
    print("📊 Beautiful desktop interface")
    print("🎨 Matching web UI design")
    print("🔧 Pure Tkinter - no dependencies")
    print("=" * 60)

    app = ModernTkinterApp()
    app.run()
