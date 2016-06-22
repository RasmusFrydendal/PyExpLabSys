
import sys
import types
import math
from pprint import pprint
from time import sleep, time, strftime
import logging
import json
from threading import Thread
logging.basicConfig(level=logging.DEBUG)
import xml.etree.ElementTree as ET
import numpy as np
from queue import Queue


import MySQLdb
CONN = MySQLdb.connect('servcinf-sql', 'cinf_reader', 'cinf_reader', 'cinfdata')
CURSOR = CONN.cursor()

# Message queue for messaging between WebSockets thread and Qt thread
MESSAGE_QUEUE = Queue()

# Qt imports
from PyQt4.QtGui import (
    QApplication, QWidget, QVBoxLayout, QGridLayout, QSpacerItem, QColor, QTableWidget,
    QLabel, QPainter
)
from PyQt4.QtCore import QTimer, QThread, QTime, QDateTime
import pyqtgraph as pg
from pyqtgraph import PlotWidget, AxisItem, PlotItem

# Websocket imports
from twisted.internet import reactor, ssl
#from twisted.python import log
#log.startLogging(sys.stdout)
from autobahn.twisted.websocket import (
    WebSocketClientProtocol, WebSocketClientFactory, connectWS
)


### DEFAULTS
print(pg.CONFIG_OPTIONS)
DEFAULTS = {
    'x_window': 600,
    'jump_ahead': 0.2,
    'color': pg.getConfigOption('foreground'),
    'line_width': 2,
    'unit': '',
    'column_defs': ('color', 'label', 'x', 'y'),
    'column_headers': ('', 'Label', 'Time', 'Value'),
    'column_widths': (None, None, 100, None),  # The last one is ignored
    'xaxis': 'time',
    'xformat': 'HH:mm:ss',
    'yformat': '.2f',
    'table_padding': 5,
    'title_size': 26,
}


### XML helpers
def typed(xml):
    """Convert XML value to Python types"""
    type_ = xml.attrib.get('type', None)
    if type_ is None:
        return xml.text

    if type_ == 'bool':
        if xml.text == 'True':
            return True
        elif xml.text == 'False':
            return False
        else:
            message = 'Invalid bool string "{}", must be "True" or "False"'
            raise ValueError(message.format(xml.text))

    # The type function may be within brackets
    type_func = getattr(__builtins__, type_.strip('[]'))
    if type_.startswith('['):
        return [type_func(value.strip()) for value in xml.text.split(',')]
    else:
        return type_func(xml.text.strip())


def xmlget(xml, element_name):
    """Get like function for xml for elements that may or may not exits"""
    # If we can find the element, Return typed version
    subelement = xml.find(element_name)
    if subelement is not None:
        return typed(subelement)
    else:
        return DEFAULTS.get(element_name)


### Helpers
def getcolor(color_def):
    """Make a QColor"""
    try:
        color = pg.mkColor(color_def)
    except:
        color = QColor(color_def)
        if not color.isValid():
            raise ValueError('Invalid color def {}'.format(color_def))
    return color


## Custom pyqtgraph hacks
def tickStringsDate(self, values, scale, spacing):
    """Return HH:mm:ss strings from unixtime values"""
    # FIXME Change date format depending of min max value
    # FIXME Make better date locator
    out = []
    for value in values:
        t = QDateTime()
        t.setTime_t(value)
        out.append(t.toString('HH:mm:ss'))
    return out


def tickValuesLog(self, minVal, maxVal, size):
    """Return tick values for log scale

    NOTE: For log scales minVal and maxVal is log to the values

    Includes fix for missing ticks for small log scales
    """
    # Get original result
    original_result = self._old_tickValues(minVal, maxVal, size)

    # Check how many ticks there are in total
    sumticks = 0
    for level in original_result:
        sumticks += len(level[1])
    # If there are less than 2, make some
    if sumticks < 2:
        # Simple logscale of the exponents for 10 **
        tickvalues = np.linspace(minVal, maxVal, 5)
        # In order to sure that the digits we are not showing is 0,
        # ask how the tick strings will look
        tickstrings = self.tickStrings(tickvalues, None, None)
        # And then convert the tick strings back into ticks YIKES
        return [(None, list(tickvalues))]
    return original_result


def tickStringsLog(self, values, scale, spacing):
    """Return tick strings for values on log scale

    Increases the number of digits until there are no duplicate strings
    """
    values = 10 ** np.array(values).astype(float)
    places = 1
    strings = ['identical', 'identical']
    while len(set(strings)) != len(strings):  # Look for duplicates
        places += 1
        strings = ['{{:.{}e}}'.format(places).format(x) for x in values]
    return strings
    


clog = logging.getLogger('CinfFigure')
class Cinfpyqtgraph(PlotWidget):
    """Custom pyqtgraph with a little data handling"""

    def __init__(self, parent, xmlconf, background='default', include_old_data=True):
        """Initialize local variables"""
        self.include_old_data = include_old_data
        # Extract title and labels
        title = xmlget(xmlconf, 'title')
        clog.debug('Title: %s', title)
        labels = {}
        for label_element in xmlconf.findall('label'):
            labels[label_element.attrib['position']] = label_element.text

        # Call init on pyqtgraph
        super(Cinfpyqtgraph, self).__init__(
            parent=parent, background=background, labels=labels,
            # There seems to be a bug in pyqtgraph FIXME
            #axisItems={'left': BetterAxisItem(orientation='left')},
        )

        # Set title
        title_size = xmlget(xmlconf, 'title_size')
        self.setTitle(title, size='{}px'.format(title_size))

        # Set logscale
        ylogscale = xmlget(xmlconf, 'ylogscale')
        self.setLogMode(y=ylogscale)

        # Ugly monkey patching hack because we cannot supply our own axis
        baxis = self.getAxis('bottom')
        baxis.tickStrings = types.MethodType(tickStringsDate, baxis)
        laxis = self.getAxis('left')
        if laxis.logMode:
            laxis._old_tickValues = laxis.tickValues
            laxis.tickValues = types.MethodType(tickValuesLog, laxis)
            laxis.tickStrings = types.MethodType(tickStringsLog, laxis)

        # Set size
        self.xmlconf = xmlconf
        size = xmlget(xmlconf, 'size')
        self.setFixedSize(*size)

        # Set the x window
        self.current_window = None
        self.x_window = xmlget(xmlconf, "x_window")
        self.jump_ahead = xmlget(xmlconf, "jump_ahead")
        clog.debug('x_window: %s, jump_ahead: %s', self.x_window, self.jump_ahead)
        self.set_x_window()

        # Form curves
        self.curves = {}
        self.data = {}
        for curve_def in xmlconf.findall('plot'):
            data_channel = curve_def.find('data_channel').text

            # Get line style options and make pen
            color = getcolor(xmlget(curve_def, 'color'))
            linewidth = xmlget(curve_def, 'line_width')
            pen = pg.mkPen(color=color, width=linewidth)

            # Make initial data
            old_data_query = xmlget(curve_def, 'old_data_query')
            if old_data_query is not None and self.include_old_data:
                CURSOR.execute(old_data_query.format(**{'from': self.current_window[0]}))
                data = [[], []]
                for point in CURSOR.fetchall():
                    data[0].append(point[0])
                    data[1].append(point[1])
                self.data[data_channel] = data
            else:
                self.data[data_channel] = [[], []]

            # Add the curve
            self.curves[data_channel] = self.plot(*self.data[data_channel], pen=pen)

            # Check if this curve has a label
            label_def = curve_def.find('label')
            if label_def is not None and 'table' in label_def.attrib:
                table = label_def.attrib['table']
                parent.tables[table].add_row(data_channel, label_def, curve_def, color)

    def process_data_batch(self, data):
        host = data['host']
        for codename, value in data['data'].items():
            sub_def = '{}:{}'.format(host, codename)
            curve = self.curves.get(sub_def)
            if curve is not None:
                self.data[sub_def][0].append(value[0])
                self.data[sub_def][1].append(value[1])
                curve.setData(*self.data[sub_def])
                if value[0] > self.current_window[1]:
                    self.set_x_window()
                    self.shave_data()

    def set_x_window(self):
        """Set the X-window"""
        now = time()
        self.current_window = (
            now - self.x_window * (1 - self.jump_ahead),
            now + self.x_window * self.jump_ahead
        )
        self.setXRange(*self.current_window)

    def shave_data(self):
        """Shave old data off the list"""
        xstart = self.current_window[0]
        for sub_def, data in self.data.items():
            for n, value in enumerate(data[0]):
                if value > xstart:                    
                    cut = max(n - 1, 0)
                    break
            else:
                cut = 0
            if cut != 0:
                data[0] = data[0][cut:]
                data[1] = data[1][cut:]


class FloatLabel(QLabel):
    def __init__(self, text, parent, str_format, unit):
        self.formatter = '{{:{}}} {}'.format(str_format, unit)
        super(FloatLabel, self).__init__(text=text, parent=parent)

    def setValue(self, value):
        """Set the text with a value from a float"""
        super(FloatLabel, self).setText(self.formatter.format(value))        


class DateLabel(QLabel):
    def __init__(self, text, parent, date_format):
        self.date_format = date_format
        self.t = QDateTime()
        super(DateLabel, self).__init__(text=text, parent=parent)

    def setValue(self, unixtimestampe):
        """Set the text with a value from a unix timestamp"""
        self.t.setTime_t(unixtimestampe)
        super(DateLabel, self).setText(self.t.toString(self.date_format))


class ColorWidget(QWidget):
    def __init__(self, color, table_padding, parent=None):
        super(ColorWidget, self).__init__(parent=parent)
        self.color = color
        self.table_padding = table_padding

    def paintEvent(self, event):

        qp = QPainter()
        qp.begin(self)
        qp.setPen(self.color)
        qp.setBrush(self.color)
        d = min(self.height(), self.width()) - self.table_padding
        qp.drawEllipse(self.width() // 2 - d // 2, self.height() // 2 - d // 2, d, d)
        qp.end()


tlog = logging.getLogger('CinfQTable')
class CinfQTable(QTableWidget):

    def __init__(self, parent, table_def):
        super(CinfQTable, self).__init__(parent=parent)
        self.table_def = table_def
        self.rows = {None: []}
        self.row_index = {}
        self.x_widgets = {}
        self.y_widgets = {}

    def add_row(self, data_channel, label_def, curve_def, color):
        """Add row to table"""
        label = label_def.text
        unit = xmlget(curve_def, 'unit')
        row = {'data_channel': data_channel, 'label': label, 'unit': unit,
               'color': color}
        if 'position' in label_def.attrib:
            position = int(label_def.attrib['position'])
            self.rows[position] = row
        else:
            self.rows[None].append(row)
        tlog.debug("Add row to label table: %s", row)

    def finalize_table(self):
        """Finalize the tables"""
        tlog.debug("FINALIZE")
        unsorted = self.rows.pop(None)
        keys = set(self.rows.keys())
        sorted_keys = sorted(keys)
        if not list(sorted_keys) == list(range(len(sorted_keys))):
            message = "Explicit table positions must be consequtive. Got: {}"
            raise ValueError(message.format(sorted_keys))
        for row in unsorted:
            index = len(self.rows)
            self.rows[index] = row

        column_defs = xmlget(self.table_def, 'column_defs')
        self.setColumnCount(len(column_defs))
        self.setRowCount(len(self.rows))
        table_padding = xmlget(self.table_def, 'table_padding')
        for column_count, column_def in enumerate(column_defs):
            for row_count, row in self.rows.items():
                widget = None
                if column_def == 'color':
                    widget = ColorWidget(row['color'], table_padding=table_padding)
                elif column_def == 'label':
                    widget = QLabel(text=row['label'])
                    height = widget.height()
                    widget.resize(100, 100)
                elif column_def == 'x':
                    str_format = xmlget(self.table_def, 'xformat')
                    if xmlget(self.table_def, 'xaxis') == 'time':
                        widget = DateLabel(text='-', parent=None, date_format=str_format)
                    else:
                        widget = FloatLabel(text='-', parent=None, str_format=str_format)
                    self.x_widgets[row['data_channel']] = widget
                elif column_def == 'y':
                    str_format = xmlget(self.table_def, 'yformat')
                    widget = FloatLabel(text='-', parent=None, str_format=str_format,
                                        unit=row['unit'])
                    self.y_widgets[row['data_channel']] = widget
                else:
                    raise ValueError('Unknown column def: {}'.format(column_def))
                if widget is not None:
                    tlog.debug('For column: "%s" set label %s position, %s, %s',
                               column_def, widget, row_count, column_count)
                    self.setCellWidget(row_count, column_count, widget)

        # Fix widths
        settings_widths = xmlget(self.table_def, 'column_widths')
        for column_count, column_def in enumerate(column_defs[:-1]):
            settings_width = settings_widths[column_count]
            if settings_width is not None:
                self.setColumnWidth(column_count, settings_width)
                continue

            if column_def == 'color':
                height = self.rowHeight(0)
                self.setColumnWidth(column_count, height)
            elif column_def == 'label':
                width = max([self.cellWidget(row_count, column_count).sizeHint().width()
                             for row_count in range(len(self.rows))])
                self.setColumnWidth(column_count, width + table_padding)
            else:
                pass

        header = self.horizontalHeader()
        header.setStretchLastSection(True)

        # Set headers
        self.setHorizontalHeaderLabels(xmlget(self.table_def, 'column_headers'))
        

    def process_data_batch(self, data):
        host = data['host']
        for codename, value in data['data'].items():
            sub_def = '{}:{}'.format(host, codename)
            for dat, widgets in zip(value, (self.x_widgets, self.y_widgets)):
                widget = widgets.get(sub_def)
                if widget is not None:
                    widget.setValue(dat)




klog = logging.getLogger('kiosk')
class AThread(QThread):

    def run(self):
        """Main threaded method"""
        klog.info("run in data thread started")
        cinfkiosk = self.parent()

        MESSAGE_QUEUE.put(cinfkiosk.subscriptions)
        while MESSAGE_QUEUE.qsize() > 0:
            sleep(1E-6)

        while True:
            item = MESSAGE_QUEUE.get()
            #klog.debug('Got data item %s', item)
            if item == 'STOP':
                break
            cinfkiosk.process_data_batch(item)
        klog.info('run in data thread stopped')



class CinfKiosk(QWidget):
    """Cinf Kiosk main app"""
    
    def __init__(self, settings_file, screen_geometry, include_old_data=True):
        """Init local variables"""
        klog.debug('Init')
        super(CinfKiosk, self).__init__()
        self.xml = ET.parse(settings_file).getroot()
        self.screen_geometry = screen_geometry
        self.include_old_data = include_old_data

        # Apply local defaults
        defaults = self.xml.find('defaults')
        if defaults is not None:
            for element in defaults:
                DEFAULTS[element.tag] = typed(element)

        self.figures = {}
        self.tables = {}
        self.init_ui()

        data_channels = [e.text for e in self.xml.findall('.//data_channel')]
        klog.info("Data channels: %s", data_channels)
        self.subscriptions = {
            u'action': u'subscribe',
            u'subscriptions': data_channels
        }


        self.data_thread = AThread(self)
        #thread.finished.connect(app.exit)
        self.data_thread.start()
        #sys.exit(app.exec_())
        
        
    def init_ui(self):
        """Init the UI"""
        klog.debug('init_ui')
        self.setWindowTitle('Cinfkiosk')
        #self.setWindowIcon(QIcon('web.png'))

        layout = QGridLayout(self)
        
        # Add graphs
        # FIXME Maybe flowlayout, gridlayout or anchorlayout
        max_column = 0
        max_row = 0
        for xmldef in self.xml.findall('table') + self.xml.findall('figure'):
            id_ = xmldef.attrib['id']
            if xmldef.tag == "figure":
                # Make the figure
                if id_ in self.figures:
                    raise ValueError('The graph id must be unique. "{} already known"'\
                                     .format(id_))
                klog.debug("Add figure: %s", id_)
                element = Cinfpyqtgraph(self, xmldef,
                                        include_old_data=self.include_old_data)
                self.figures[id_] = element
            else:
                element = CinfQTable(parent=self, table_def=xmldef)
                self.tables[id_] = element

            # Add it to the grid layout
            # grid is [row, column, rowspan, columnspan] or [row, column]
            grid = typed(xmldef.find('grid'))
            # Pad 1's for the row and column span if necessary
            grid = grid + [1] * (4 - len(grid))
            klog.debug("Add to grid %s", grid)
            max_column = max(max_column, grid[1] + grid[3] - 1)
            max_row = max(max_row, grid[0] + grid[2] - 1)
            layout.addWidget(element, *grid)

        for table in self.tables.values():
            table.finalize_table()


        klog.debug("Add spacer to %s, %s", max_row + 1, max_column + 1)
        layout.addItem(QSpacerItem(1, 1), max_row + 1, max_column + 1)
        layout.setColumnStretch(max_column + 1, 1)
        layout.setRowStretch(max_row + 1, 1)
        self.setLayout(layout)

        klog.debug('show')
        self.showMaximized()
        self.show()

    def process_data_batch(self, databatch):
        """Receive data"""
        for table in self.tables.values():
            table.process_data_batch(databatch)
        for fig in self.figures.values():
            fig.process_data_batch(databatch)

    def closeEvent(self, event):
        klog.info('close event')
        MESSAGE_QUEUE.put('STOP')
        while self.data_thread.isRunning():
            sleep(1E-6)
        super(CinfKiosk, self).closeEvent(event)
        


WEBSOCKET_CLIENT = None
wslog = logging.getLogger('WebSocket')
class MyClientProtocol(WebSocketClientProtocol):

    def onConnect(self, response):
        """onConnection call back"""
        global WEBSOCKET_CLIENT
        WEBSOCKET_CLIENT = self
        wslog.debug("Server connected: %s", response.peer)

    def onOpen(self):
        subscribe = MESSAGE_QUEUE.get()
        self.sendMessage(json.dumps(subscribe).encode('ascii'))
        wslog.debug("WebSocket connection open.")

    def onMessage(self, payload, isBinary):

        MESSAGE_QUEUE.put(json.loads(payload.decode('utf8')))
        #wslog.debug("Text message received: %s", payload.decode('utf8'))

    def onClose(self, wasClean, code, reason):
        wslog.debug("WebSocket connection closed: %s", reason)


if __name__ == '__main__':
    factory = WebSocketClientFactory(url="wss://cinf-wsserver.fysik.dtu.dk:9002")
    factory.protocol = MyClientProtocol

    if factory.isSecure:
        contextFactory = ssl.ClientContextFactory()
    else:
        contextFactory = None

    connectWS(factory, contextFactory)
    Thread(target=reactor.run, args=(False,)).start()
    #t = MyThread(reactor)

    app = QApplication(sys.argv)
    ex = CinfKiosk(
        'kiosksettings.xml',
        screen_geometry=app.desktop().screenGeometry(),
        include_old_data=False,
    )
    ret = app.exec_()

    # Stop websocket connection and reactor
    WEBSOCKET_CLIENT.sendClose()
    while WEBSOCKET_CLIENT.state != WEBSOCKET_CLIENT.STATE_CLOSED:
        sleep(1E-3)
    reactor.stop()

    sys.exit(ret)


### Graph
# Modified from https://gist.github.com/friendzis/4e98ebe2cf29c0c2c232
# class TimeAxisItem(AxisItem):
#     def __init__(self, *args, **kwargs):
#         super(TimeAxisItem, self).__init__(*args, **kwargs)

#     def tickStrings(self, values, scale, spacing):
#         """Return HH:mm:ss strings from unixtime values"""
#         out = []
#         for value in values:
#             t = QDateTime()
#             t.setTime_t(value)
#             out.append(t.toString('HH:mm:ss'))
#         return values


# class BetterAxisItem(AxisItem):
#     pass
