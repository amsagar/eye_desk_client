import datetime
import threading
import time
import platform
import tkinter as tk
from io import BytesIO
from PIL import ImageGrab
import requests
import config
from firebase_admin import credentials, storage
import firebase_admin
import json
import os
import subprocess
import sys
from Activity import UserFocusThread

app_data_dir = '.eyedesk'
root_path = os.path.expanduser('~')
full_path = os.path.join(root_path, app_data_dir)
json_file_path = os.path.join(full_path, 'login_status.json')

try:
    if not os.path.exists(full_path):
        os.makedirs(full_path)

    username = os.getlogin() if sys.platform.startswith('win') else os.getlogin()

    if sys.platform.startswith('win'):
        subprocess.run(['icacls', full_path, '/grant', f'{username}:(OI)(CI)F'], check=True)
    else:
        os.chmod(full_path, 0o700)

    if not os.path.exists(json_file_path):
        login_data = {"logged_in": False, "email": "", "password": "", "id": 0, "name": ""}
        with open(json_file_path, "w") as file:
            json.dump(login_data, file)

    print("Hidden app data directory created at:", full_path)
    print("JSON file created at:", json_file_path)
    with open(json_file_path, "r") as file:
        print(json.load(file))
except Exception as e:
    print("Error:", e)


def download_acc_json(url):
    response = requests.get(url)
    response.raise_for_status()  # Raise an exception for HTTP errors
    return response.json()


def save_login_status(email, client, name, password):
    login_data = {"logged_in": True, "email": email, "password": password, "id": client, "name": name}
    with open(get_json_path(), "w") as file:
        json.dump(login_data, file)


def remove_login_status():
    try:
        with open(get_json_path(), "r") as file:
            login_status = json.load(file)
        login_status['logged_in'] = False
        with open(get_json_path(), "w") as file:
            json.dump(login_status, file)
    except FileNotFoundError:
        pass


def get_json_path():
    return json_file_path


class LoginApp:
    def __init__(self, appRoot):
        self.ap_label = None
        self.error_label = None
        self.start_button = None
        self.stop_button = None
        self.focus_thread = None
        self.screenshot_thread = None
        self.result = None
        self.elapsed_time = None
        self.login_button = None
        self.password_entry = None
        self.password_label = None
        self.email_entry = None
        self.email_label = None
        self.name_label1 = None
        self.name_label = None
        self.stop_event = threading.Event()
        self.start_time = None
        self.t = None
        self.timer_job = None
        self.timer_label = None
        self.root = appRoot
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)
        self.root.title("EYE-DESK")
        self.logged_in = False
        self.running = False
        self.timer_thread = None
        json_url = config.ACC_CLOUD_URL
        try:
            acc_json_content = download_acc_json(json_url)
            self.cred = credentials.Certificate(acc_json_content)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(self.cred, {'storageBucket': 'eyedesk-43706.appspot.com'})
            self.bucket = storage.bucket()
            self.client_id = None
            if self.check_logged_in():
                self.show_home_screen()
            else:
                self.show_login_screen()
        except Exception as e:
            print("Error downloading or loading credentials:", e)
            self.show_error_screen()
        with open(get_json_path(), "r") as file:
            login_status = json.load(file)
        print(login_status)

        # if not firebase_admin._apps:
        #     self.cred = credentials.Certificate(
        #         "/Users/sagar/Desktop/eyedesk_client/acc.json")
        #     firebase_admin.initialize_app(self.cred, {'storageBucket': 'eyedesk-43706.appspot.com'})

    def show_login_screen(self):
        self.clear_screen()
        self.ap_label = tk.Label(self.root, text="EYE-DESK", fg='black', bg='#2ab0ff', font=("Arial", 52))
        self.ap_label.grid(row=0, column=0, columnspan=2, pady=5)
        self.name_label = tk.Label(self.root, text="Welcome to EyeDesk!", font=("Arial", 18), fg='black', bg='#2ab0ff')
        self.name_label.grid(row=1, column=0, columnspan=2, pady=5)

        self.name_label1 = tk.Label(self.root, text="Login Here", font=("Arial", 16), fg='black', bg='#2ab0ff')
        self.name_label1.grid(row=2, column=0, columnspan=2, pady=5)

        self.email_label = tk.Label(self.root, text="Email:", font=("Arial", 22), fg='black', bg='#2ab0ff')
        self.email_label.grid(row=3, column=0, padx=10, pady=5, sticky="e")

        self.email_entry = tk.Entry(self.root, fg='black', bg='white')
        self.email_entry.grid(row=3, column=1, padx=10, pady=5)

        self.password_label = tk.Label(self.root, text="Password:", font=("Arial", 22), fg='black', bg='#2ab0ff')
        self.password_label.grid(row=4, column=0, padx=10, pady=5, sticky="e")

        self.password_entry = tk.Entry(self.root, show="*", fg='black', bg='white')
        self.password_entry.grid(row=4, column=1, padx=10, pady=5)

        self.login_button = tk.Button(self.root, text="Login", command=self.login)
        self.login_button.grid(row=5, column=0, columnspan=2, pady=10)

    def login(self):
        email = self.email_entry.get()
        password = self.password_entry.get()
        api_endpoint = config.LOGIN_API_URL
        payload = {"emailId": email, "password": password}
        try:
            response = requests.post(api_endpoint, json=payload)
            if response.status_code == 200:
                response_json = response.json()
                id_value = response_json.get('id')
                fullName = response_json.get('fullName')
                self.logged_in = True
                save_login_status(email, id_value, fullName, password)
                self.update_json()
                with open(get_json_path(), "r") as file:
                    login_status = json.load(file)
                print(login_status)
                self.show_home_screen()
            else:
                self.show_error_message("Invalid email or password")
        except Exception as e:
            self.show_error_message('API Request Error' + str(e))

    def check_logged_in(self):
        try:
            with open(get_json_path(), "r") as file:
                login_status = json.load(file)
                if login_status.get("logged_in"):
                    api_endpoint = config.LOGIN_API_URL
                    payload = {"emailId": login_status.get('email'), "password": login_status.get('password')}
                    try:
                        response = requests.post(api_endpoint, json=payload)
                        if response.status_code == 200:
                            self.update_json()
                            return True
                        else:
                            return False
                    except Exception as e:
                        return False
                return False
        except FileNotFoundError:
            return False

    def show_error_message(self, message):
        error_message = tk.Label(self.root, text=message, font=("Arial", 12), fg='red', bg='#2ab0ff')
        error_message.grid(row=7, column=0, columnspan=2, pady=5)
        self.root.after(5000, error_message.destroy)

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def show_home_screen(self):
        self.clear_screen()
        self.ap_label = tk.Label(self.root, text="EYE-DESK", fg='black', bg='#2ab0ff', font=("Arial", 52))
        self.ap_label.grid(row=0, column=0, columnspan=2, pady=5)
        with open(get_json_path(), "r") as file:
            login_status = json.load(file)
        home_label = tk.Label(self.root, text="Welcome!\n" + login_status.get("name"), font=("Arial", 18), fg='black',
                              bg='#2ab0ff')
        home_label.grid(row=1, column=0, columnspan=2, pady=5)
        logout_button = tk.Button(self.root, text="Logout", command=self.logout)
        logout_button.grid(row=2, column=0, columnspan=2, pady=5)
        now = datetime.datetime.now()
        date_label = tk.Label(self.root, text=now.strftime("%Y-%m-%d"), font=("Arial", 18), fg='black', bg='#2ab0ff')
        date_label.grid(row=3, column=0, columnspan=2, pady=5)
        if login_status.get("timer") and login_status.get('date') == now.strftime("%Y-%m-%d"):
            self.t = login_status.get("timer")
        else:
            self.t = datetime.time(hour=0, minute=0, second=0)
            login_status['timer'] = "00:00:00"
            login_status['date'] = now.strftime("%Y-%m-%d")
        with open(get_json_path(), "w") as file:
            json.dump(login_status, file)
        # print(str(self.t))
        self.timer_label = tk.Label(self.root, text=str(self.t), font=("Arial", 20))
        self.timer_label.grid(row=4, column=0, columnspan=2, pady=5)
        self.start_button = tk.Button(self.root, text="Start Timer", command=lambda: self.timer(self.t))
        self.start_button.grid(row=5, column=0, columnspan=2, pady=5)
        self.stop_button = tk.Button(self.root, text="Stop Timer", command=self.getTrackingDetails)
        self.stop_button.grid(row=6, column=0, columnspan=2, pady=5)
        self.stop_button.config(state='disabled')

    def timer(self, date_string):
        if not isinstance(date_string, str):
            date_string = date_string.strftime("%H:%M:%S")
        self.running = True
        self.timer_thread = threading.Thread(target=self.start_timer, args=(date_string,))
        self.screenshot_thread = threading.Thread(target=self.capture_screenshots)
        self.focus_thread = UserFocusThread()
        self.focus_thread.start()
        self.screenshot_thread.start()
        self.timer_thread.start()

    def start_timer(self, date_string):
        initial_time = datetime.datetime.now()
        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.display_timer(initial_time, date_string)

    def display_timer(self, initial_time, date_string):
        current_time = datetime.datetime.now()
        self.elapsed_time = current_time - initial_time
        formatted_time = str(self.elapsed_time).split('.')[0]
        time1_delta = datetime.datetime.strptime(formatted_time, "%H:%M:%S")
        time2_delta = datetime.datetime.strptime(date_string, "%H:%M:%S")
        self.result = time1_delta + (time2_delta - datetime.datetime.strptime("00:00:00", "%H:%M:%S"))
        self.timer_label.config(text=str(self.result.time()))
        if self.running:
            self.root.after(1000, self.display_timer, initial_time, date_string)

    def getTrackingDetails(self):
        self.running = False
        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
        threading.Thread(target=self.updater).start()

    def updater(self):
        self.timer_thread.join()
        self.stop_event.set()
        self.screenshot_thread.join()
        self.t = str(self.result.time())
        with open(get_json_path(), "r") as file:
            login_status = json.load(file)
        login_status['timer'] = self.t
        with open(get_json_path(), "w") as file:
            json.dump(login_status, file)
        self.focus_thread.stop()
        self.focus_thread.join()
        time.sleep(1)
        total_activity = self.focus_thread.mouse_activity + self.focus_thread.keyboard_activity
        max_mouse_activity = 60 * 10
        max_keyboard_activity = 60 * 10
        # total_max_activity = max_mouse_activity + max_keyboard_activity
        # focus_score_percentage = min((total_activity / total_max_activity) * 100,
        #                              100)
        # print(focus_score_percentage)
        weighted_total_activity = (2 * self.focus_thread.mouse_activity) + self.focus_thread.keyboard_activity
        weighted_total_max_activity = (2 * max_mouse_activity) + max_keyboard_activity
        focus_score_percentage = min((weighted_total_activity / weighted_total_max_activity) * 100, 100)
        print(focus_score_percentage)
        self.focus_thread.mouse_activity = 0
        self.focus_thread.keyboard_activity = 0
        self.show_error_message("User focus score:" + str(focus_score_percentage) + "%")
        # print("User focus score:", focus_score_percentage * 100, "%")
        self.stop_event.clear()
        with open(get_json_path(), "r") as file:
            login_status = json.load(file)
        api_endpoint = config.DAILY_UPDATE_API_URL
        payload = {"date": login_status.get('date'), "dailyActivity": focus_score_percentage,
                   'dailyHours': self.t, 'client': login_status.get('id')}
        try:
            response = requests.post(api_endpoint, json=payload)
            if response.status_code == 200:
                pass
        except Exception as e:
            self.show_error_message(str(e))

    # api call

    def capture_screenshots(self):
        interval = 180
        with open(get_json_path(), "r") as file:
            login_status = json.load(file)
        while not self.stop_event.is_set():
            try:
                screenshot = ImageGrab.grab()
                screenshot_bytes = BytesIO()
                screenshot.save(screenshot_bytes, format='PNG')
                screenshot_bytes.seek(0)
                destination_blob_name = str(login_status.get('id')) + "/screenshot_{0}.png".format(time.time())
                blob = self.bucket.blob(destination_blob_name)
                blob.upload_from_file(screenshot_bytes, content_type='image/png')
                expiration = datetime.datetime.now() + datetime.timedelta(days=365 * 100)
                url = blob.generate_signed_url(expiration=expiration, version='v2')
                with open(get_json_path(), "r") as file:
                    login_status = json.load(file)
                screenshot_data = {
                    "client": login_status.get('id'),
                    "url": url,
                    "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                    "time": str(datetime.datetime.now().time())
                }
                api_endpoint = config.SCREENSHOT_UPDATE_API_URL
                response = requests.post(api_endpoint, json=screenshot_data)
                if response.status_code == 201:
                    self.show_error_message('ScreenShot Captured')
                try:
                    pass
                except Exception as e:
                    self.show_error_message(str(e))
                if self.stop_event.wait(interval):
                    time.sleep(1)
            except KeyboardInterrupt:
                break

    def update_json(self):
        with open(get_json_path(), "r") as file:
            login_status = json.load(file)
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        client_id = login_status.get('id')
        api_endpoint = f"{config.GET_DAILY_HOURS_API_URL}?date={date}&client_id={client_id}"
        try:
            response = requests.get(api_endpoint)
            # print(response.json())
            if response.status_code == 200:
                response_json = response.json()
                dailyHours = response_json.get('dailyHours')
                login_status['timer'] = str(dailyHours)
                login_status['date'] = date
                with open(get_json_path(), "w") as file:
                    json.dump(login_status, file)
        except Exception as e:
            # print("ass", e)
            self.show_error_message('API Request Error')

    def logout(self):
        self.logged_in = False
        remove_login_status()
        self.show_login_screen()

    def show_error_screen(self):
        self.clear_screen()
        self.error_label = tk.Label(self.root, text="Please connect to Internet and Restart", font=("Arial", 18),
                                    fg='red', bg='#2ab0ff')
        self.error_label.grid(row=0, column=0, columnspan=2, pady=5)


def main_application(root):
    LoginApp(root)


def resource_path():
    base_path = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base_path, 'icon.png')


if __name__ == "__main__":
    root = tk.Tk()
    root.title("EYE-DESK")
    root.configure(bg="#2ab0ff")
    system = platform.system()
    if system == "Darwin":
        root.geometry('500x380')
    elif system == "Windows":
        root.geometry('750x580')
    logo_image = tk.PhotoImage(file=resource_path(), height=200, width=200)
    logo_label = tk.Label(root, image=logo_image)
    logo_label.pack(pady=10)
    app_label = tk.Label(root, text="EYE-DESK", fg='black', bg='#2ab0ff', font=("Arial", 52))
    app_label.pack(pady=20)
    loading_label = tk.Label(root, text="Loading, please wait...", fg='black', bg='#2ab0ff', font=("Arial", 32))
    loading_label.pack(pady=1)
    root.after(1000, lambda: main_application(root))
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - root.winfo_reqwidth()) / 2
    y = (screen_height - root.winfo_reqheight()) / 2
    root.geometry("+%d+%d" % (x, y))
    root.mainloop()
