from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle,Paragraph
from reportlab.lib.units import inch, mm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.rl_config import defaultPageSize
from reportlab.lib.pagesizes import A4
from reportlab.platypus import PageBreak
from reportlab.platypus import Image
from reportlab.lib.utils import ImageReader
import datetime
import numpy as np
from matplotlib import dates
import matplotlib.pyplot as plt
import io

# based on https://github.com/JohnFunkCode/dataframetopdf

class PDFReport(object):
    def __init__(self,name):
        self.doc = SimpleDocTemplate(name, pagesize=A4)
        self.docElements = []
        #setup the package scoped global variables we need
        now = datetime.datetime.now()
        PDFReport.timestamp = now.strftime("%Y-%m-%d %H:%M")
        PDFReport.sourcefile = "not initialized"
        PDFReport.pageinfo = "not initialized"
        PDFReport.Title = "not initialized"
        PDFReport.PAGE_HEIGHT = defaultPageSize[1];
        PDFReport.PAGE_WIDTH = defaultPageSize[0]
        PDFReport.styles = getSampleStyleSheet()   #sample style sheet doesn't seem to be used

    def set_title(self,title):
        self.doc.title = title
        
    def set_author(self,author):
        self.doc.author = author

    @staticmethod
    def set_pageInfo(pageinfo):
        PDFReport.pageinfo = pageinfo

    @staticmethod
    def set_sourcefile(sourcefile):
        PDFReport.sourcefile = sourcefile

    def put_dataframe_on_pdfpage(self, df):
        #table with observations
        elements = []

        # Data Frame
        if df is not None:
            t = Table(df)
            t.setStyle(TableStyle([('FONTNAME', (0, 0), (-1, -1), "Helvetica"),
                                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                                ('BACKGROUND',(0,0), (-1,0),colors.silver),
                                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                                ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.black),
                                ('BOX', (0, 0), (-1, -1), 0.25, colors.black)]))
            elements.append(t)
        else:
            #no data
            styles = getSampleStyleSheet()
            title_style = styles['Heading3']
            title_style.alignment = 1
            title_style.textColor='red'
        
            p = Paragraph("NO observations!",title_style)
            elements.append(p)
            elements.append(Spacer(1,0.2*inch))
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(PageBreak())


        self.docElements.extend(elements)

        return elements;
    
    def put_notes_on_pdfpages(self,gen_notes,meteo_notes):
        #general and meteo notes
        elements = []

        # Title
        styles = getSampleStyleSheet()
        title_style = styles['Heading3']
        title_style.alignment = 1
        styleN = styles["BodyText"]
        styleN.alignment = 4
        
        p = Paragraph("General notes",title_style)
        elements.append(p)
        elements.append(Spacer(1,0.2*inch))     
        
        note1=Paragraph(gen_notes,styleN)
        elements.append(note1)
        elements.append(Spacer(1,0.2*inch))
        
        p = Paragraph("Meteo notes",title_style)
        elements.append(p)
        elements.append(Spacer(1,0.2*inch))  
        
        note2=Paragraph(meteo_notes,styleN)
        elements.append(note2)
        elements.append(Spacer(1,0.2*inch))
        
        elements.append(PageBreak())

        self.docElements.extend(elements)
        
        return elements;
        

    def put_meteo_on_pdfpage(self, df, seeing=None):
        #graphs and table with meteo data
        elements = []

        # Title
        styles = getSampleStyleSheet()
        title_style = styles['Heading3']
        title_style.alignment = 1
        p = Paragraph("Weather statistics",title_style)
        elements.append(p)
        elements.append(Spacer(1,0.2*inch))

        # Data Frame
        meteo=[['','Min','Max','Median']]
        meteo.append(['Temperature',round(np.nanmin(df['temp']),1),round(np.nanmax(df['temp']),1),round(np.nanmedian(df['temp']),1)])
        meteo.append(['Humidity',round(np.nanmin(df['hum']),1),round(np.nanmax(df['hum']),1),round(np.nanmedian(df['hum']),1)])
        meteo.append(['Pressure',round(np.nanmin(df['press']),1),round(np.nanmax(df['press']),1),round(np.nanmedian(df['press']),1)])

        def WindDir(wd):
            #convert azimut to direction of wind
            wind_dirs={np.nan:np.nan,'N':0,'NNE':22.5,'NE':45,'ENE':67.5,'E':90,'ESE':112.5,'SE':135,'SSE':157.5,\
               'S':180,'SSW':202.5,'SW':225,'WSW':247.5,'W':270,'WNW':292.5,'NW':315,'NNW':337.5}
            x0='N'
            for x in list(wind_dirs)[::-1]:
                if wd>=wind_dirs[x]+22.5/2.: return x0
                else: x0=x
            return 'N'

        wmin=np.nanargmin(df['wind'])
        wmax=np.nanargmax(df['wind'])
        wmean=np.rad2deg(np.arctan2(np.nanmedian(np.sin(np.deg2rad(df['winddir']))),np.nanmedian(np.cos(np.deg2rad(df['winddir'])))))
        meteo.append(['Wind speed','%.1f (%s)' %(np.nanmin(df['wind']),WindDir(df['winddir'][wmin])),'%.1f (%s)' %(np.nanmax(df['wind']),WindDir(df['winddir'][wmax])),'%.1f (%s)' %(np.nanmedian(df['wind']),WindDir(wmean))])
        meteo.append(['Pyrgeo',round(np.nanmin(df['clouds']),1),round(np.nanmax(df['clouds']),1),round(np.nanmedian(df['clouds']),1)])
        if seeing is None: meteo.append(['Seeing','---','---','---'])
        else: meteo.append(['Seeing',round(np.nanmin(seeing[:,1]),1),round(np.nanmax(seeing[:,1]),1),round(np.nanmedian(seeing[:,1]),1)])   

        t = Table(meteo)
        t.setStyle(TableStyle([('FONTNAME', (0, 0), (-1, -1), "Helvetica"),
                               ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                               ('BACKGROUND',(0,0), (-1,0),colors.silver),
                               ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                               ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.black),
                               ('BOX', (0, 0), (-1, -1), 0.25, colors.black)]))
        elements.append(t)
        elements.append(Spacer(1, 0.2 * inch))

        x=dates.date2num(df['dt'])
        hfmt=dates.DateFormatter('%H:%M')

        def fig2image(f):
            #save image to buffer
            buf = io.BytesIO()
            f.savefig(buf, format='png', dpi=300)
            buf.seek(0)
            x, y = f.get_size_inches()
            return Image(buf, x * inch, y * inch)

        fig, axs = plt.subplots(3,2,dpi=300,figsize=(8,7))
        axs[0,0].plot(x,df['temp'],'.')
        axs[0,0].set_ylabel('Temperature (C)')
        axs[0,1].plot(x,df['hum'],'.')
        axs[0,1].set_ylabel('Humidity (%)')
        #limit
        if axs[0,1].get_ylim()[1]>90: axs[0,1].axhline(y=90,color='r')
        if axs[0,1].get_ylim()[1]>70: axs[0,1].axhline(y=70,color='orange',linestyle='--')
        axs[1,0].plot(x,df['wind'],'.')
        axs[1,0].set_ylabel('Wind speed (m/s)')
        #limit
        if axs[1,0].get_ylim()[1]>17: axs[1,0].axhline(y=17,color='r')
        if axs[1,0].get_ylim()[1]>8: axs[1,0].axhline(y=8,color='orange',linestyle='--')
        axs[1,1].plot(x,df['winddir'],'.')
        axs[1,1].set_ylabel('Wind direction (deg)')
        axs[2,0].plot(x,df['clouds'],'.')
        axs[2,0].set_ylabel('Pyrgeo (Clouds)')
        #limit
        if axs[2,0].get_ylim()[1]>-70: axs[2,0].axhline(y=-70,color='r')
        if axs[2,0].get_ylim()[1]>-80: axs[2,0].axhline(y=-80,color='orange',linestyle='--')        
        if seeing is None: axs[2,1].remove()
        else: 
            axs[2,1].plot(dates.date2num(seeing[:,0]),seeing[:,1],'.')
            axs[2,1].set_ylabel('Seeing = FWHM (arcsec)')
            axs[2,1].set_xlim(axs[2,0].get_xlim())
        for i in range(3):
            for j in range(2):
                axs[i,j].xaxis.set_major_formatter(hfmt)
        
        plt.tight_layout()

        elements.append(fig2image(fig))

        elements.append(PageBreak())

        self.docElements.extend(elements)

        return elements;

    def write_pdfpage(self):
        self.doc.build(self.docElements, onFirstPage=first_page_layout, onLaterPages=page_layout)


# define layout for first page
def first_page_layout(canvas, doc):
    canvas.saveState()
    canvas.setFont('Times-Bold', 16)
    canvas.drawCentredString(PDFReport.PAGE_WIDTH / 2.0, PDFReport.PAGE_HEIGHT-0.5 * inch, 'Observing log')
    #add logo
    logo = ImageReader('logo.png')
    canvas.drawImage(logo, 10*mm, PDFReport.PAGE_HEIGHT-20*mm,width=50*mm,height=10*mm, mask='auto',preserveAspectRatio=True)
    
    canvas.setFont('Times-Bold', 14)
    canvas.drawCentredString(PDFReport.PAGE_WIDTH / 2.0, PDFReport.PAGE_HEIGHT-0.75 * inch, 'Observing date: '+doc.title)
    canvas.setFont('Times-Roman', 9)
    canvas.drawString(inch * 3, 0.75 * inch,
                      "Page: %d     Generated: %s     " % (
                      doc.page, PDFReport.timestamp))
    canvas.restoreState()

# define layout for subsequent pages
def later_page_layout(canvas, doc):
    canvas.saveState()
    canvas.setFont('Times-Roman', 9)
    canvas.drawString(inch, 0.75 * inch, "Page %d %s" % (doc.page, PDFReport.pageinfo))
    canvas.restoreState()

# define layout for subsequent pages
def page_layout(canvas, doc):
    canvas.saveState()
    canvas.setFont('Times-Roman', 9)
    canvas.drawString(inch * 3, 0.75 * inch,
                      "Page: %d     Generated: %s     " % (
                      doc.page, PDFReport.timestamp))
    canvas.restoreState()
