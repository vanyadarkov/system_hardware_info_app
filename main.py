from PyQt5.uic import loadUi
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from threading import Thread
import sys
from time import sleep
import socket
import clr # din pythonnet, nu clr

openhardwaremonitor_hwtypes = ['CPU','GpuNvidia','GpuAti']
openhardwaremonitor_sensortypes = ['Clock','Temperature','Load','Fan','Power']

def put_metrics(sensor_type, sensor_value):
        if sensor_type == 'Temperature':
            return u"%d\N{DEGREE SIGN}C" % (sensor_value)
        if sensor_type == 'Clock':
            return u"%d MHz" % (sensor_value)
        if sensor_type == 'Load':
            return u"%d%%" % (sensor_value)
        if sensor_type == 'Fan':
            return u"%d RPM" % (sensor_value)
        if sensor_type == 'Power':
            return u"%d W" % (sensor_value)
        
def get_new_value(computer, hardware, sensor_type, sensor_name):
    for i in computer.Hardware:
        if(str(i.Name) == hardware):
            i.Update()
            for sensor in i.Sensors:
                if(str(sensor.SensorType) == sensor_type and str(sensor.Name) == sensor_name):
                    return put_metrics(str(sensor.SensorType), sensor.Value)
    return ""

def get_total_usage_and_temp(computer, hwtype):
    temperature = 0
    usage = 0
    for i in computer.Hardware:
        if(hwtype == 0 and str(i.HardwareType) == 'CPU'):
            i.Update()
            for sensor in i.Sensors:
                if(str(sensor.SensorType) == 'Temperature' and 'Package' in str(sensor.Name)):
                    temperature = sensor.Value
                if(str(sensor.SensorType) == 'Load' and 'Total' in str(sensor.Name)):
                    usage = sensor.Value
        elif (hwtype == 1 and (str(i.HardwareType) == 'GpuNvidia' or str(i.HardwareType) == 'GpuAti')):
            i.Update()
            for sensor in i.Sensors:
                if(str(sensor.SensorType) == 'Temperature' and 'Core' in str(sensor.Name)):
                    temperature = sensor.Value
                if(str(sensor.SensorType) == 'Load' and 'Core' in str(sensor.Name)):
                    usage = sensor.Value
    return usage, temperature

class Worker(QObject):
    computer = None
    treeWidget = None
    
    def __init__(self, computer, treeWidget) -> None:
        super().__init__()
        self.computer = computer
        self.treeWidget = treeWidget
    
    def run(self):
        root = self.treeWidget.invisibleRootItem()
        root_child_count = root.childCount()
        while True:
            for i in range(root_child_count):
                root_item = root.child(i)
                for j in range(root_item.childCount()):
                    hardware = root_item.child(j)
                    for k in range(hardware.childCount()):
                        sensor_type = hardware.child(k)
                        for l in range(sensor_type.childCount()):
                            sensor_child = sensor_type.child(l)
                            sensor_child.setText(1, get_new_value(self.computer, hardware.text(0), sensor_type.text(0), sensor_child.text(0)))
                            QApplication.processEvents()
            self.treeWidget.update()
        

class Monitor(QMainWindow):
    clr.AddReference(r'OpenHardwareMonitorLib')
    from OpenHardwareMonitor import Hardware
    computer = Hardware.Computer()
    
    def __init__(self) -> None:
        super().__init__()
        loadUi('monitor.ui', self)

        self.computer.MainboardEnabled = True
        self.computer.CPUEnabled = True
        self.computer.GPUEnabled = True
        self.computer.Open()
        self.init_tree()
        
        self.monitor_tree_thread_q = QThread()
        self.monitor_tree_thread = Worker(self.computer, self.treeWidget)
        self.monitor_tree_thread_q.started.connect(self.monitor_tree_thread.run)
        self.monitor_tree_thread.moveToThread(self.monitor_tree_thread_q)
        self.monitor_tree_thread_q.start()
        
        self.cpu_graph_init()
        self.gpu_graph_init()
        
    def init_tree(self):
        self.treeWidget.setHeaderLabels(['Sensor','Value'])
        root = QTreeWidgetItem([socket.gethostname()])
        self.treeWidget.addTopLevelItem(root);
        
        for i in self.computer.Hardware:
            if(str(i.HardwareType) in openhardwaremonitor_hwtypes):
                child = QTreeWidgetItem([str(i.Name)])
                
                list = []
                added_childs = []
                i.Update()
                for sensor in i.Sensors:
                    if str(sensor.SensorType) in openhardwaremonitor_sensortypes:
                        if str(sensor.SensorType) in list:
                            sensor_child = added_childs[list.index(str(sensor.SensorType))]
                        else : 
                            sensor_child = QTreeWidgetItem([str(sensor.SensorType)])
                            list.append(str(sensor.SensorType))
                            added_childs.append(sensor_child)
                        sensor_info_child = QTreeWidgetItem([str(sensor.Name)])
                        sensor_info_child.setText(1, put_metrics(str(sensor.SensorType), sensor.Value))
                        
                        sensor_child.addChild(sensor_info_child)
                        child.addChild(sensor_child)
                        root.addChild(child)
                        sensor_child.setExpanded(True)
                        sensor_info_child.setExpanded(True)
                        child.setExpanded(True)
                        root.setExpanded(True)
                        
                list = []
                added_childs = []
            
    def cpu_graph_init(self):
        self.plotCpuWidget.setTitle('CPU')
        self.plotCpuWidget.showGrid(x = True, y = True)
        self.plotCpuWidget.setLabel('left', 'Information')
        self.plotCpuWidget.setLabel('bottom', 'Time', units='s')
        self.plotCpuWidget.addLegend()
        self.plotCpuWidget.setYRange(-5, 105, padding=0)
        self.plotCpuWidget.setMouseEnabled(x = False, y = False)
        
        self.cpu_plot_thread = Thread(target=self.cpu_graph_plot)
        self.cpu_plot_thread.daemon = True
        self.cpu_plot_thread.start()
        
    def gpu_graph_init(self):
        self.plotGpuWidget.setTitle('GPU')
        self.plotGpuWidget.showGrid(x = True, y = True)
        self.plotGpuWidget.setLabel('left', 'Information')
        self.plotGpuWidget.setLabel('bottom', 'Time', units='s')
        self.plotGpuWidget.addLegend()
        self.plotGpuWidget.setYRange(-5, 105, padding=0)
        self.plotGpuWidget.setMouseEnabled(x = False, y = False)
        
        self.gpu_plot_thread = Thread(target=self.gpu_graph_plot)
        self.gpu_plot_thread.daemon = True
        self.gpu_plot_thread.start()

    def cpu_graph_plot(self):
        self.plotCpuWidget.clear()
        seconds = []
        usages = []
        temperatures = []
        s = -1
        self.plotCpuWidget.plot(seconds, usages, name = 'Usage (%)', pen = 'r')
        self.plotCpuWidget.plot(seconds, temperatures, name = 'Temperature (\N{DEGREE SIGN}C)', pen = 'g')
        while True:
            s += 1
            usage, temperature = get_total_usage_and_temp(self.computer, 0)
            usages.append(usage)
            temperatures.append(temperature)
            seconds.append(s)
            self.plotCpuWidget.plot(seconds, usages, pen = 'r')
            self.plotCpuWidget.plot(seconds, temperatures, pen = 'g')
            sleep(1)
            
    def gpu_graph_plot(self):
        self.plotGpuWidget.clear()
        seconds = []
        usages = []
        temperatures = []
        s = -1
        self.plotGpuWidget.plot(seconds, usages, name = 'Usage (%)', pen = 'r')
        self.plotGpuWidget.plot(seconds, temperatures, name = 'Temperature (\N{DEGREE SIGN}C)', pen = 'g')
        while True:
            s += 1
            usage, temperature = get_total_usage_and_temp(self.computer, 1)
            usages.append(usage)
            temperatures.append(temperature)
            seconds.append(s)
            self.plotGpuWidget.plot(seconds, usages, pen = 'r')
            self.plotGpuWidget.plot(seconds, temperatures, pen = 'g')
            sleep(1)

if __name__ == '__main__':
    qApp = QApplication([])
    monitor = Monitor()
    monitor.setFixedSize(monitor.size())
    monitor.show()
    
    try:
        sys.exit(qApp.exec_())
        
    except SystemExit:
        print("Exit")