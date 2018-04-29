import wrapper as wmi
import datetime
import json

class Connection:
    def __init__(self, ip, username, password, journals):
        self.ip = ip
        self.username = username
        self.password = password
        self.journals = journals
        self.wmic = wmi.WmiClientWrapper(username=self.username, password=self.password, host=self.ip)

connections = []
connections.append(
    Connection("5.79.106.192","wmiagent","KqZckCHD9T",['Security', 'System', 'Application'])
)

def convert_time(wmi_date):
    year = int(wmi_date[4])
    month = int(wmi_date[4:6])
    day = int(wmi_date[6:8])
    hours = int(wmi_date[8:10])
    minutes = int(wmi_date[10:12])
    seconds = int(wmi_date[12:14])
    return datetime(year, month, day, hours, minutes, seconds)

def inverse_convert_time(python_date):
    return datetime.datetime.strftime(python_date, "%Y%m%d%H%M%S")+'.000000-000'

time = inverse_convert_time(datetime.datetime.now() - datetime.timedelta(minutes=1))
for c in connections:
    output = c.wmic.query('SELECT * FROM Win32_NTLogEvent WHERE (Logfile = "System" or Logfile = "Security" or Logfile = "Applications") and TimeWritten > "{}"'.format(time))

for event in output:
    print json.dumps(event)
