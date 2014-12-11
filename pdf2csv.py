import sys, re
from itertools import *
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfdevice import PDFDevice
from pdfminer.pdfpage import PDFPage
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams, LTTextBoxHorizontal, LTLine, LTRect
from pdfminer.converter import PDFPageAggregator

TEXT_HEIGHT=12.0

class TextItem:
    """
    container class to hold a line of text contained in the pdf
    
    attributes: 
    text (item text)
    x0, x1, y0, y1: bounding box coordinates
    """
    def build_pdf(self, pdfobj):
        """build an item from the pdf object representing it"""
        self.text = pdfobj.get_text()
        self.x0, self.x1 = pdfobj.x0, pdfobj.x1
        self.y0, self.y1 = pdfobj.y0, pdfobj.y1
    def build_textitem(self, textobj):
        """create a deep copy"""
        self.text = textobj.text
        self.x0, self.x1 = textobj.x0, textobj.x1
        self.y0, self.y1 = textobj.y0, textobj.y1
    def __init__(self, pdfobj=None):
        if pdfobj:
            self.build_pdf(pdfobj)
    def __repr__(self):
        return "TextItem(%s %.1f %.1f)"%(repr(self.text), self.y0, self.y1)

def get_pdf_contents(filename):
    """
    open a pdf file and return a list of pages containing its contents.

    Each page in this list contains:
    -a list of columns of text (each column is a list of TextItems)
    -a list of the y-coordinates of all horizontal lines on the page
    """
    #read the pdf
    fp = open(filename, 'rb')
    parser = PDFParser(fp)
    document = PDFDocument(parser, "password")
    if not document.is_extractable:
        raise PDFTextExtractionNotAllowed
    rsrcmgr = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmgr, device)

    pages = []
    #cols are hardcoded, based on inspecting coordinates of example documents
    cols = [(12, 85), (85, 233), (233, 305), (305, 382), 
            (382, 558), (558, 661), (661, 779)]
    hlines = []

    for page in PDFPage.create_pages(document):
        contents = [[] for c in cols]
        hlines = []
        interpreter.process_page(page)
        layout = device.get_result()
        
        #find all horizontal textboxes, and check if they lie inside a 
        #pre-defined column. If yes, add them to the page
        for child in layout:
            if isinstance(child, LTTextBoxHorizontal):
                for i, col in enumerate(cols):
                    if child.x0 >= col[0] and child.x1 <= col[1]:
                        contents[i].append(TextItem(child))
            #add horizontal lines
            elif isinstance(child, LTLine) or isinstance(child, LTRect):
                if (abs(child.y0 - child.y1) < 2 and 
                    abs(child.x0 - child.x1) > 10):
                    hlines.append(child.y0)
        pages.append((contents, hlines))
    return pages

def split_item(item, hlines):
    """split the item into two if there's an hline running through it"""
    for line in hlines:
        if line >= item.y0 and line <= item.y1:
            arr = item.text.splitlines()
            #guess which newline to split at by estimating the height of text
            split_index = int(round((item.y1 - line)/TEXT_HEIGHT))
            it1 = TextItem()
            it2 = TextItem()
            it1.build_textitem(item)
            it2.build_textitem(item)
            it1.text = ' '.join(arr[:split_index])
            it1.y0 = line + 1
            it2.y1 = line - 1
            it2.text = ' '.join(arr[split_index:])
            if it1.text == "" or it2.text == "":
                if it1.text == "":
                    item.y1 = line - 1
                else:
                    item.y0 = line + 1
                return [item]
            return [it1, it2]
    return [item]
    

def collect_item(prev_items, next_item, hlines):
    """collect the next item into a list of lists"""
    #if item is in same row as previous, add it to the last list
    #otherwise, make a new list
    if not prev_items:
        return [[next_item]]
    if same_item(prev_items[-1][-1], next_item, hlines):
        prev_items[-1].append(next_item)
        return prev_items
    else:
        prev_items.append([next_item])
        return prev_items

def same_item(item1, item2, hlines):
    """return true if these two items lie in the same row"""
    if item1.y1 > item2.y0:
        item1, item2 = item2, item1
    for line in hlines:
        if line > item1.y0 and line < item2.y1:
            return False
        elif line > item2.y1:
            return True
    return True

def collapse_item(item_list):
    """collapse a list of items all in the same row to a single string"""
    item_str = reduce(lambda x, y: x + y.text, item_list, "")
    return re.sub(' +', ' ', item_str.replace('\n', ' ')).strip()

def process_column(col, hlines):
    """turn list of pdf objects in a column into meaningful data
    
    return a list of strings. Each string in the list represents
    data for exactly one case.
    """
    col.sort(key=lambda item: -1 * item.y0)
    col = [split_item(item, hlines) for item in col]
    col = [it for split in col for it in split]
    col = reduce(lambda x,y: collect_item(x,y, hlines), col, [])
    col = [collapse_item(item) for item in col]
    return col

def get_cases(data):
    """get list of formatted cases from list of columns"""
    cases = [list(row) for row in zip(*data)]
    for case in cases:
        #ignore case duration (just use start time)
        case[3] = re.sub(' *hrs.*', '', case[3])
        case[2] = re.sub(' *through.*', '', case[2])
    return cases


def get_csv_text(filename):
    """get csv data from a pdf file

    Output format:
    Report date, Incident, Date, Time, Location, Disposition, Case #
    
    Duration of events is ignored (date/time occured represents only
    the event start time)
    """
    out_cases = []
    pages = get_pdf_contents(filename)
    for page in pages:
        #get pdf text objects and horizontal line coords
        contents, hlines = page
        hlines.sort()
        #data is organized by columns. use hlines to ensure each item
        #in a column is data for exactly one case
        data = [process_column(col, hlines) for col in contents]
        
        #sometimes, we're missing the header in the first column since it
        #gets absorbed by the Chief Ronnell Higgins text box
        if re.match(r'\d\d?/\d\d?/\d\d\d\d', data[0][0]):
            data[0].insert(0,"Date reported")
            
        #delete all headers
        data = [col[1:] for col in data]
        cases = get_cases(data)
        for case in cases:
            out_cases.append(", ".join(case))
    return "\n".join(out_cases)
