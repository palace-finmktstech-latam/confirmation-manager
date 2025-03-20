from app.main import app, start_email_monitor
import threading
import argparse
import os
from flask import Flask

monitor_thread = None

# Use Flask's current approach for initialization
@app.route('/start-monitoring', methods=['GET'])
def start_monitoring_route():
    parser = argparse.ArgumentParser(description='Start the confirmation management application.')
    parser.add_argument('--entity', required=True, help='Entity name to use as "This Party"')
    args = parser.parse_args()

    os.environ['MY_ENTITY'] = args.entity

    global monitor_thread
    if not monitor_thread or not monitor_thread.is_alive():
        print("Starting email monitoring thread")
        monitor_thread = threading.Thread(target=start_email_monitor)
        monitor_thread.daemon = True
        monitor_thread.start()
    return "Monitoring started"

# Immediately start monitoring when app starts
with app.app_context():
    start_monitoring_route()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5005, debug=True)