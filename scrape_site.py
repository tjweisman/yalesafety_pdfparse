#!/usr/bin/python

import pdf2csv, datetime, urllib, os
from pdfminer.pdfparser import PDFSyntaxError

TEMP_FILENAME="tmp.pdf"
URL_BASE = "http://publicsafety.yale.edu/sites/default/files/%s.pdf"

def get_csv(date):
    """get csv data for cases on a particular date"""
    url = URL_BASE%date.strftime("%m%d%y")
    
    urllib.urlretrieve(url, TEMP_FILENAME)
    try:
        out = "%s\n"%pdf2csv.get_csv_text(TEMP_FILENAME)
    except PDFSyntaxError:
        #this wasn't a pdf file
        out = ""
    #cleanup
    os.remove(TEMP_FILENAME)

    return out

def get_csv_range(start_date, end_date, out_filename):
    """write a csv file with case data for all days between start_date
    and end_date, inclusive"""

    if start_date > end_date:
        return
    day = datetime.timedelta(1)
    date = start_date
    fp = open(out_filename, 'w')
    while date <= end_date:
        fp.write(get_csv(date))
        date += day

#write a csv file for all cases in October 2014
get_csv_range(datetime.date(2014, 10, 1), 
              datetime.date(2014, 10, 31), "october.csv")
