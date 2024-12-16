import sys
import matplotlib
matplotlib.use('Agg')
from astropy.io import fits
import glob
import pandas as pd
from astropy.coordinates import AltAz, EarthLocation, SkyCoord
import astropy.units as u
import os,json
import PDFReportClass as pdf
import datetime
from fwhm import *
from snr import SNR


def header(name):
    '''read fits header'''
    hdu=fits.open(name)[0]
    header=hdu.header

    if 'IMAGETYP' not in header:
        #return None
        typ='test'

        #filename=os.path.basename(name)
        #date=header['FRAME']
        #exp=int(round(header['EXPOSURE']))

        #tmp=filename.split('_')
        #obj='_'.join(tmp[3:])
        #obj=obj[:obj.rfind('.')]

        #typ='test'

#         if name in notes_all:
#             notes=notes_all[name].strip()
#             #wrap very long notes into separate lines...
#             i=0
#             notes1=''
#             while len(notes[i:])>20:
#                 notes1+=notes[i:i+20]+'\n'
#                 i+=20
#
#             notes1+=notes[i:]
#         else:
#             notes=''
#             notes1=''
#
#         i=0
#         obj1=''
#         #wrap very long target names into separate lines...
#         while len(obj[i:])>20:
#             obj1+=obj[i:i+20]+'\n'
#             i+=20
#         obj1+=obj[i:]

        #return {'object':obj,'type':'test','datetime':date,'exposure':exp,'ra':'','dec':'','filename':filename,'temp':None,'hum':None,
        #    'clouds':None,'wind':None,'winddir':None,'press':None,'altitude':None,'airmass':None,'notes':notes,'ra1':'','dec1':'','notes1':notes1,'object1':obj1,'snr':''}
    else:
        typ=header['IMAGETYP']
        #obj=header['OBJECT']
        #date=header['DATE-OBS']

    if 'OBJECT' in header: obj=header['OBJECT'].strip()
    else:
        filename=os.path.basename(name)
        tmp=filename.split('_')
        obj='_'.join(tmp[3:])
        obj=obj[:obj.rfind('.')]

    if 'DATE-OBS' in header:
        date=header['DATE-OBS']
        if ':' not in date:
            T=date.find('T')+1
            date=date[:T+2]+':'+date[T+2:T+4]+':'+date[T+4:]
    else: date=header['FRAME']


    exp=int(round(header['EXPOSURE']))

    #get coordinates
    if 'TCS COORDINATES RA' in header:
        #pucheros
        ra0=header['TCS COORDINATES RA']
        d=ra0.find('.')
        ra=ra0[:d-4]+':'+ra0[d-4:d-2]+':'+ra0[d-2:]

        dec0=header['TCS COORDINATES DEC']
        d=dec0.find('.')
        dec=dec0[:d-4]+':'+dec0[d-4:d-2]+':'+dec0[d-2:]

        lon=header['GEOLON']
        lat=header['GEOLAT']
        ele=header['GEOELEV']
    elif 'RA' in header:
        #platospec
        ra=header['RA']
        dec=header['DEC']
        #d=dec0.find('.')
        #dec=dec0[:d-4]+':'+dec0[d-4:d-2]+':'+dec0[d-2:]
        lon=header['LONGITUD']
        lat=header['LATITUDE']
        ele=header['HEIGHT']
    else: ra='None'

    if ra.strip()=='None':
        ra=''
        dec=''
        alt=''
        air=''
        ra1=''
        dec1=''
    else:
        #d=ra0.find('.')
        #ra=ra0[:d-4]+':'+ra0[d-4:d-2]+':'+ra0[d-2:]

        #dec=header['DEC']
        #d=dec0.find('.')
        #dec=dec0[:d-4]+':'+dec0[d-4:d-2]+':'+dec0[d-2:]
        #lon=header['LONGITUD']
        #lat=header['LATITUDE']
        #ele=header['HEIGHT']

        #calculate altitude and airmass of target
        star=SkyCoord(ra,dec,unit=(u.hourangle, u.deg))
        obs=EarthLocation(lon=lon*u.deg,lat=lat*u.deg,height=ele*u.m)

        altaz=star.transform_to(AltAz(obstime=date,location=obs))
        alt=round(altaz.alt.deg,1)
        air=round(altaz.secz.value,1)

        #compact format for report
        ra1=ra[:ra.find('.')]
        dec1=dec[:dec.find('.')]

    if 'FRONTEND_POSITION2' in header:
        if header['FRONTEND_POSITION2']>79000 and header['FRONTEND_POSITION2']<100000: ic='no'
        elif header['FRONTEND_POSITION2']<2000 and header['FRONTEND_POSITION2']>50: ic='yes'
        else: ic='err'
    else: ic=''

    if 'SIMULT' in header:
        #if header['SIMULT']=='THAR_CU': simult='ThAr'
        #elif header['SIMULT']=='I2_CU': simult='IC'
        #elif header['SIMULT']=='OFF' and ('ttarget' in obj or 'tcomp' in obj or 'tflat' in obj):

        flat=header['CU_FLAT_LAMP_1']
        ic_lamp=header['CU_FLAT_LAMP_2']
        comp=(header['CU_COMP_LAMP_1'] or header['CU_COMP_LAMP_2'])
        filt1=header['CU_FILTER_1']
        filt2=header['CU_FILTER_2']
        apfilt1=header['CU_APPLIED_FILTER_1']
        apfilt2=header['CU_APPLIED_FILTER_2']
        compU=header['CU_COMP_LAMP_VOLTAGE']
        compI=header['CU_COMP_LAMP_CURRENT']
        cu_ic=header['CU_IODINE_CELL']
        flatU=header['CU_DEMANDED_LED_LAMP_CURRENT']

        if compU>100 and compI>5: comp=True
        else: comp=False
        
        #if flatU>10: flat=True
        #else: flat=False

        if apfilt2=='FILTER_CLOSED': simult='off'
        else:
            if ic_lamp and cu_ic and not (comp or flat): simult='IC'
            elif comp and not (flat or ic_lamp): simult='ThAr'
            elif flat and not (comp or ic_lamp): simult='flat'
            elif (not flat) and (not comp) and (not ic_lamp): simult='off'
            else: simult='err'

        #else: simult='off'
    else: simult=''

    #get meteo data


    # elif header['METEO_TEMPERATURE'].strip()=='None':
    #     temp=None
    #     hum=None
    #     clouds=None
    #     wind=None
    #     wind_dir=None
    #     press=None
    if 'METEO TEMPERATURE' in header:
        if header['METEO TEMPERATURE'].strip()=='None':
            temp=None
            hum=None
            clouds=None
            wind=None
            wind_dir=None
            press=None
        else:
            temp=float(header['METEO TEMPERATURE'])
            hum=float(header['METEO HUMIDITY'])
            clouds=float(header['METEO PYRGEOMETER'])
            wind=float(header['METEO WIND SPEED'])
            wind_dir=float(header['METEO WIND DIRECTION'])
            press=float(header['METEO ATMOSPHERIC PRESSURE'])
    elif 'METEO_TEMPERATURE' in header:
        temp=float(header['METEO_TEMPERATURE'])
        hum=float(header['METEO_HUMIDITY'])
        clouds=float(header['METEO_PYRGEOMETER'])
        wind=float(header['METEO_WIND_SPEED'])
        wind_dir=float(header['METEO_WIND_DIRECTION'])
        press=float(header['METEO_ATMOSPHERIC_PRESSURE'])
    else:
        temp=None
        hum=None
        clouds=None
        wind=None
        wind_dir=None
        press=None

    if name in notes_all:
        notes=notes_all[name].strip()
        #wrap very long notes into separate lines...
        i=0
        notes1=''
        while len(notes[i:])>16:
            notes1+=notes[i:i+16]+'\n'
            i+=16

        notes1+=notes[i:]
    else:
        notes=''
        notes1=''

    i=0
    obj1=''
    #wrap very long target names into separate lines...
    while len(obj[i:])>16:
        obj1+=obj[i:i+16]+'\n'
        i+=16
    obj1+=obj[i:]

    if typ.lower()=='science' or typ=='test' and not obj.lower() in ['bias','zero','flat','comp','test','thar','dark']:
        snr=int(round(SNR(name,mask='sim-mask.dat')))
    else: snr=''

    return {'object':obj,'type':typ,'datetime':date,'exposure':exp,'ra':ra,'dec':dec,'filename':os.path.basename(name),'temp':temp,'hum':hum,
            'clouds':clouds,'wind':wind,'winddir':wind_dir,'press':press,'altitude':alt,'airmass':air,'notes':notes,'ra1':ra1,'dec1':dec1,
            'notes1':notes1,'object1':obj1,'snr':snr,'ic':ic,'simult':simult}

#meteo guider? - probably take very long time (number of files...)
#fits header -> OCHUM, OCWINDD, OCWINDS, OCTEMP, OCPGM


#path to folder with guider images
guider='guider/'                 # Y/Y-m-d data from guider
guider0=guider                   # guider - incoming
#guider='guider/'
#guider0=guider
guider_res=0.134    #resolution arcsec/px

#folder to spectra -> to make log
folder='data/2024-11-26'
if len(sys.argv)>1:
    folder=sys.argv[1]

if not folder[-1]=='/': folder+='/'
date=folder.strip().split('/')[-2]

#load notes form json
notes_all={}
if os.path.isfile('notes/'+date+'.json'):
    f=open('notes/'+date+'.json','r')
    notes_all=json.load(f)
    f.close()

#load general and meteo notes -> modify newlines
if 'general' in notes_all: gen_notes=notes_all['general'].replace('\n','<br />\n')
else: gen_notes=''
if 'meteo' in notes_all: meteo_notes=notes_all['meteo'].replace('\n','<br />\n')
else: meteo_notes=''

#load fits file and read header
data0=[]
if os.path.isdir(folder+'fits'): folder+='fits/'
for name in sorted(glob.glob(folder+'20*.fits')):
    info=header(name)
    if info is not None: data0.append(info)

#date of report
date=folder.strip().split('/')[-2]
if date=='.': date=''

p=pdf.PDFReport('logs/'+date+'_log.pdf')
p.set_title(date)
p.set_author('Nightlog')

if len(data0)>0:
    #convert to df, add date and time
    df=pd.DataFrame(data0)
    dt=pd.to_datetime(df['datetime'],format='%Y-%m-%dT%H:%M:%S.%f',utc=True)
    df['dt']=dt
    df['time']=dt.dt.strftime('%H:%M:%S')
    df['date']=dt.dt.strftime('%Y-%m-%d')

    #fwhn calculation
    fwhm_dt=[]
    fwhm_vals=[]
    if os.path.isfile('fwhm/'+date+'_fwhm.dat'):        #used already calculated values
        f=open('fwhm/'+date+'_fwhm.dat','r')
        for l in f:
            if l[0]=='#': continue
            tmp=l.split()
            d=tmp[0]
            t=tmp[1]
            fx=float(tmp[-2])
            fy=float(tmp[-1])
            fwhm_dt.append(datetime.datetime.strptime(d+' '+t, "%Y-%m-%d %H:%M:%S"))
            fwhm_vals.append((fx+fy)/2)
        f.close()
    elif datetime.datetime.strptime(date, "%Y-%m-%d") > datetime.datetime.strptime('2024-05-01', "%Y-%m-%d"):   #calculate only for new frontend
        date_guider=datetime.datetime.strptime(date, "%Y-%m-%d")

        #Chile Linux2
        path=guider+date_guider.strftime("%Y/%Y-%m-%d/")
        if not os.path.isdir(path): path=guider0

        f=open('fwhm/'+date+'_fwhm.dat','w')
        f.write('# date      time      FWHM_X(px)      FWHM_Y(px)      FWHM_X(arcsec)      FWHM_Y(arcsec)\n')
        for name in sorted(glob.glob(path+'y'+date_guider.strftime("%Y%m%d")+'*.fit')):
            #analyze all guider images
            dt,px_x,px_y=fwhm(name)
            if len(px_x)*len(px_y)==0: continue
            #mean value from all stars on 1 image
            px_x=np.mean(px_x)
            px_y=np.mean(px_y)
            f.write('%s      %.2f      %.2f      %.2f      %.2f\n' %(dt,px_x,px_y,px_x*guider_res,px_y*guider_res))
            fwhm_dt.append(datetime.datetime.strptime(dt, "%Y-%m-%d %H:%M:%S"))
            fwhm_vals.append((px_x+px_y)/2*guider_res)   #mean value of fwhm in arcsec
        f.close()

    #make csv log
    df[['object','date','time','exposure','altitude','airmass','ra','dec','notes','filename','snr','ic','simult']].to_csv('logs/'+date+'_log.csv',index=False)

    #rename cols and convert df for pdf
    df2=df[['object1','time','exposure','altitude','airmass','ra1','dec1','snr','simult','ic','notes1']].rename(columns={'ra1': 'ra', 'dec1': 'dec','notes1':'notes','object1':'object','simult':'sim'})
    data = [df2.columns[:, ].values.astype(str).tolist()] + df2.values.tolist()

    #add data (params of fits) to pdf
    p.put_dataframe_on_pdfpage(data)

    #add notes
    p.put_notes_on_pdfpages(gen_notes,meteo_notes)

    #add meteo and fwhm data
    if not df['temp'].isnull().all():
        if len(fwhm_vals)>0: p.put_meteo_on_pdfpage(df,np.column_stack((fwhm_dt,fwhm_vals)))
        else: p.put_meteo_on_pdfpage(df)

else:
    #NO data!
    f=open('logs/'+date+'_log.csv','w')
    f.write('object,date,time,exposure,altitude,airmass,ra,dec,notes,filename\n')
    f.close()

    p.put_dataframe_on_pdfpage(df=None)
    p.put_notes_on_pdfpages(gen_notes,meteo_notes)

#write pdf to file
p.write_pdfpage()

#change file permissions
os.chmod('logs/'+date+'_log.csv', 0o666)
os.chmod('logs/'+date+'_log.pdf', 0o666)

#log already created -> start new night
dt=datetime.datetime.strptime(date,"%Y-%m-%d")
new=dt+datetime.timedelta(days = 1)
obs=new.strftime("%Y-%m-%d")

last_log=datetime.datetime.strptime(sorted(glob.glob('logs/*_log.pdf'))[-1],"logs/%Y-%m-%d_log.pdf")
last_notes=datetime.datetime.strptime(sorted(glob.glob('notes/*.json'))[-1],"notes/%Y-%m-%d.json")

last=max(last_log,last_notes)
now=datetime.datetime.now()

if new>last and new-now>datetime.timedelta(days=-1) and not os.path.isfile('notes/'+obs+'.json'):
    f=open('notes/'+obs+'.json','w')
    json.dump({},f)
    f.close()
    os.chmod('notes/'+obs+'.json', 0o666)


