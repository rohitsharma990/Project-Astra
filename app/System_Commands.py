import ctypes
import os
def lock_screen():
   ctypes.windll.user32.LockWorkStation()


def shutdown():
  shutdown = input("Do you wish to shutdown your computer ? (yes / no): ")

  if shutdown == 'no':
    exit()
  else: 
    os.system("shutdown /s /t 1")

def restart():
    restart = input("Do you wish to restart your computer ? (yes / no): ")
    if restart == 'no':
        exit()
    else:
     os.system("shutdown /r /t 1")