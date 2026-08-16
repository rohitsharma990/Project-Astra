menu=[
"Open Notepad",
"Open Calculator",
"Open Chrome",
"Open YouTube",
"Create Folder",
"Create File",
"Find File",
"Play Music",
"Pause Music",
"Shutdown",
"Restart",
"Lock",
"Sleep",
"Show Time",
"Spotify",
"VS Code",
"Take Screenshot",
"Notes",
"Todos",
"Memory",
"System Info",
"Exit",

]

def Menuloop():
 from app import ui

 for i in menu:
    ui.info(i)