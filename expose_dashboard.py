import os
import sys
import threading
import time
from pyngrok import ngrok

def launch_dashboard():
    print("🚀 Starting Dashboard...")
    os.system("streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0 > dash.log 2>&1")

def start_ngrok():
    # Wait for streamlit to start
    time.sleep(3)
    try:
        # Open a HTTP tunnel on the default port 8501
        public_url = ngrok.connect(8501).public_url
        print(f"\n🌍 \033[92mDashboard Public URL: {public_url}\033[0m")
        print("   (Click the link above to view your bot!)\n")
        
        # Keep alive
        ngrok_process = ngrok.get_ngrok_process()
        ngrok_process.proc.wait()
    except Exception as e:
        print(f"Ngrok Error: {e}")
        print("Tip: You may need to sign up for a free token at ngrok.com and run `ngrok config add-authtoken <token>`")

if __name__ == "__main__":
    # Start streamlit in a separate thread/process is tricky, 
    # simpler to start ngrok first then blocking call for streamlit or vice versa.
    # Actually, let's just use subprocess for streamlit.
    
    import subprocess
    
    # Start Streamlit
    print("🚀 Launching Streamlit...")
    subprocess.Popen(["streamlit", "run", "dashboard.py", "--server.port", "8501", "--server.address", "0.0.0.0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Start Ngrok
    print("🌍 Establishing Secure Tunnel...")
    time.sleep(2)
    try:
        public_url = ngrok.connect(8501).public_url
        print("="*60)
        print(f"👉 \033[1;32m{public_url}\033[0m")
        print("="*60)
        print("Press Ctrl+C to stop.")
        
        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("Stopping...")
        ngrok.kill()
