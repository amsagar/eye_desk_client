import pyautogui
import threading
import time


class UserFocusThread(threading.Thread):
    def __init__(self):
        super(UserFocusThread, self).__init__()
        self.mouse_activity = 0
        self.keyboard_activity = 0
        self.is_running = True
        self.prev_mouse_position = pyautogui.position()
        self.prev_keyboard_state = set(pyautogui.KEYBOARD_KEYS)

    def run(self):
        while self.is_running:
            curr_mouse_position = pyautogui.position()
            if curr_mouse_position != self.prev_mouse_position:
                self.mouse_activity += 1
                self.prev_mouse_position = curr_mouse_position
            curr_keyboard_state = set(pyautogui.KEYBOARD_KEYS)
            if curr_keyboard_state != self.prev_keyboard_state:
                self.keyboard_activity += 1
                self.prev_keyboard_state = curr_keyboard_state
            time.sleep(1)

    def stop(self):
        self.is_running = False



