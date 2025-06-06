from flask import Flask, redirect, url_for, render_template, request, session, send_file, flash

import os
import json
import glob
import subprocess
import hashlib
import datetime
import base64
import io
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.path as mplPath

from fwhm import *
from snr import SNR

from astropy.coordinates import get_sun, AltAz, EarthLocation, SkyCoord
from astropy.time import Time, TimeDelta
import astropy.units as u
from scipy import interpolate

import logging
import gc

from werkzeug.middleware.proxy_fix import ProxyFix

# main file for web interface for platospec E152 observation notes and logs
# (c) Pavol Gajdos, 2024

app = Flask(__name__,static_url_path='/static')
app.secret_key = 'e152logs'  # Used to secure the session

# fix for proxy
app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

adminPassword = '21232f297a57a5a743894a0e4a801fc3'  # admin - CHANGE!
password='ee11cbb19052e40b07aac0ca060c23ee'         # user - CHANGE!, not used

#path to folder with spectra
path0='data/'

#path to folder with guider images
guider='guider/'                 # Y/Y-m-d data from guider
guider0=guider                   # guider - incoming
guider_res=0.134    #resolution arcsec/px

obs_lon=-70.739     #longitude of observatory

tharMax=200   # limit voltage for ThAr lamp -> broken!

#configure for logger
logHandler=logging.FileHandler('errors.log')
logHandler.setLevel(logging.DEBUG)
app.logger.addHandler(logHandler)

snr={}  #store calculated snrs
ic={}
exp={}
sim={}
postfix={}
oldsnr=''


@app.route("/", methods=['GET', 'POST'])
def main():
    global snr,oldsnr,ic,exp,sim,postfix
    '''adding notes to current obs.'''
    
    gc.collect()
    #if not session.get('logged_in'):
    #    return redirect(url_for('login', next='main'))

    #get the latest data
    if len(glob.glob(path0+'20*/'))>0:
        path=sorted(glob.glob(path0+'20*/'))[-1]
        obs=path.strip().split('/')[-2]
    else: obs='2024-01-01'

    if not obs==oldsnr:
        #reset after new night = new folder
        oldsnr=obs
        snr={}
        ic={}
        exp={}
        sim={}
        postfix={}

    #get the latest log
    if len(glob.glob('logs/*_log.pdf'))>0:
        last_log=datetime.datetime.strptime(sorted(glob.glob('logs/*_log.pdf'))[-1],"logs/%Y-%m-%d_log.pdf")
    else: last_log=datetime.datetime.now(tz=datetime.timezone.utc).replace(tzinfo=None)-datetime.timedelta(hours=14)-datetime.timedelta(days = 1)
    #get the latest notes file
    if len(glob.glob('notes/*.json'))>0:
        last_notes=datetime.datetime.strptime(sorted(glob.glob('notes/*.json'))[-1],"notes/%Y-%m-%d.json")
    else: last_notes=datetime.datetime.now(tz=datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(hours=14)

    #find the latest kind of date (log, notes, observations)
    last=max(last_log+datetime.timedelta(days = 1),last_notes,datetime.datetime.strptime(obs,"%Y-%m-%d"))
    now=datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(hours=14)

    if now.replace(tzinfo=None)-last>datetime.timedelta(days=1):
        #long gap between any data
        last=now.replace(tzinfo=None)

    #set path for the current data
    obs=last.strftime("%Y-%m-%d")
    path=path0+obs+'/'

    notes={}
    saved=False

    #load old notes
    if os.path.isfile('notes/'+obs+'.json'):
        f=open('notes/'+obs+'.json','r')
        notes=json.load(f)
        f.close()
    else:
        f=open('notes/'+obs+'.json','w')
        json.dump(notes,f)
        f.close()
        os.chmod('notes/'+obs+'.json', 0o666)

    if 'timestamp' in notes: ts0=notes['timestamp']
    else: ts0=0
    

    #list all files + split path and name
    files = {x: os.path.splitext(os.path.basename(x))[0] for x in sorted(glob.glob(path+'*.fits'))[::-1]}
    #get snr
    for f in files:
        if f not in snr:
            try:
                hdu=fits.open(f)[0]
                header=hdu.header

                if 'IMAGETYP' not in header:
                    if 'bias' in f.lower(): snr[f]=''
                    elif 'zero' in f.lower(): snr[f]=''
                    elif 'flat' in f.lower(): snr[f]=''
                    elif 'comp' in f.lower(): snr[f]=''
                    elif 'test' in f.lower(): snr[f]=''
                    elif 'thar' in f.lower(): snr[f]=''
                    elif 'dark' in f.lower(): snr[f]=''
                    else: snr[f]=SNR(f,mask='sim-mask.dat')
                elif not header['IMAGETYP'].lower()=='science': snr[f]=''
                else: snr[f]=SNR(f,mask='sim-mask.dat')

                #IC in FE
                if 'FRONTEND_POSITION2' in header:
                    if header['FRONTEND_POSITION2']>79000 and header['FRONTEND_POSITION2']<100000: ic[f]='no'
                    elif header['FRONTEND_POSITION2']<2000 and header['FRONTEND_POSITION2']>50: ic[f]='yes'
                    else: ic[f]='err'
                else: ic[f]=''

                #sim.cal. - CU
                if 'SIMULT' in header:
                    #if header['SIMULT']=='THAR_CU': sim[f]='ThAr'
                    #elif header['SIMULT']=='I2_CU': sim[f]='IC'
                    #elif header['SIMULT']=='OFF' and ('ttarget' in header['OBJECT'] or 'tcomp' in header['OBJECT'] or 'tflat' in header['OBJECT']):
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

                    if apfilt2=='FILTER_CLOSED': sim[f]='off'
                    else:
                        if ic_lamp and cu_ic and not (comp or flat): sim[f]='IC'
                        elif comp and not (flat or ic_lamp): sim[f]='ThAr'
                        elif flat and not (comp or ic_lamp): sim[f]='flat'
                        elif (not flat) and (not comp) and (not ic_lamp): sim[f]='off'
                        else: sim[f]='err'
                        
                    if compU>tharMax:
                        #broken lamp!
                        sim[f]+='-ThArErr'
                        
                    #else: sim[f]='off'
                else: sim[f]=''
                
                if 'OBJECT' in header:
                    if 'flat' in header['OBJECT'] or 'comp' in header['OBJECT']:
                        if '_' in header['OBJECT']: postfix[f]=' ('+header['OBJECT'].split('_')[1]+')'
                        else: postfix[f]=' (all)'
                    else: postfix[f]=''
                else: postfix[f]=''
                

                exp[f]=int(round(header['EXPOSURE']))

            except:
                snr[f]=''
                ic[f]=''
                sim[f]=''
                exp[f]=''
                postfix[f]=''

    if request.method == 'POST':
        notes0=dict(notes)
        #get data from form
        for x in request.form:
            #get all individual notes
            if 'fits' in x: notes[x]=request.form[x]

        notes['meteo']=request.form['meteo']
        notes['general']=request.form['general']        
        if not request.form['path']==path: notes={}
        
        if 'timestamp' in session: ts=session.get('timestamp')
        else: ts=0

        #load saved notes to web
        if ts0>ts:
            for x in notes:
                if x=='timestamp': continue                
                if x in notes0:
                    if len(notes0[x])>len(notes[x]): notes[x]=notes0[x]

        ts=time.time()
        session['timestamp'] = ts
        if 'save' in request.form or 'saveThAr' in request.form:
            notes1={'timestamp':ts}
            for x in notes:
                if x=='timestamp': continue
                #remove empty notes
                if len(notes[x])>0: notes1[x]=notes[x]
            f=open('notes/'+obs+'.json','w')
            json.dump(notes1,f)
            f.close()
            os.chmod('notes/'+obs+'.json', 0o666)

            if 'save' in request.form: saved=True

    return render_template('index.html',files=files,path=path,notes=notes,saved=saved,snr=snr,ic=ic,exp=exp,sim=sim,postfix=postfix)

@app.route('/logs', methods=['GET', 'POST'])
def logs():
    '''show generated log files'''
    #if not session.get('logged_in'):
    #    return redirect(url_for('login', next='logs'))
    gc.collect()
    
    directory = "./logs"
    file_extension=".pdf"
    error=''

    #list all log files
    if len(glob.glob(directory+'/*_log'+file_extension))>0:
        files = [os.path.splitext(os.path.basename(x))[0] for x in sorted(glob.glob(directory+'/*_log'+file_extension))[::-1]]
        obs=files[0].replace('_log','') #latest log
    else:
        files=[]
        obs=''
        error='NO log exists!'

    if request.method == 'POST':
        error=''
        if request.form['night']: obs = request.form['night']
        file_extension = request.form['type']
        
        if file_extension=='notes':
            files = [os.path.splitext(os.path.basename(x))[0] for x in sorted(glob.glob(directory+'/general*.csv'))[::-1]]
            files+=[os.path.splitext(os.path.basename(x))[0] for x in sorted(glob.glob(directory+'/meteo*.csv'))[::-1]]
        else:            
            if os.path.isfile(directory+'/'+obs+'_log'+file_extension): error=''
            else: error='NO log exists!'

        if 'download' in request.form:
            #download log for selected night
            if os.path.isfile(directory+'/'+obs+'_log'+file_extension):
                return send_file(directory+'/'+obs+'_log'+file_extension, download_name=obs+'_log'+file_extension, as_attachment=True)

    return render_template('logs.html',night=obs,type=file_extension,files=files,error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    '''login page'''
    if request.method == 'POST':
        # Get the password from the form
        entered_password = request.form.get('password')
        hashpass=hashlib.md5(entered_password.encode()).hexdigest()   #make md5 hash of input pass

        # Check if the entered password matches (compare hash)
        if hashpass == adminPassword:
            # Set session variable - admin login
            session['logged_in'] = 'admin'
            return redirect(url_for(request.args.get('next')))  #redirect to wanted page
        elif hashpass == password:
            # Set session variable - user login
            session['logged_in'] = 'user'
            if 'admin' in request.args.get('next'): flash('Incorrect password. Please try again.')
            else: return redirect(url_for(request.args.get('next')))  #redirect to wanted page
        else:
            flash('Incorrect password. Please try again.')
    gc.collect()
    
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    '''modify notes for old observations'''
    if not session.get('logged_in'):
        return redirect(url_for('login', next='admin'))
    if not session.get('logged_in')=='admin':
        return redirect(url_for('login', next='admin'))
    
    gc.collect()
    
    notes={}
    saved=False

    #find the latest kind of date (log, notes, observations)
    if len(glob.glob(path0+'20*/'))>0:
        last_fits=datetime.datetime.strptime(sorted(glob.glob(path0+'20*/'))[-1],path0+'%Y-%m-%d/')
    else: last_fits=datetime.datetime.now(tz=datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(hours=14)
    if len(glob.glob('notes/*.json'))>0:
        last_notes=datetime.datetime.strptime(sorted(glob.glob('notes/*.json'))[-1],"notes/%Y-%m-%d.json")
    else: last_notes=datetime.datetime.now(tz=datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(hours=14)
    last=max(last_fits,last_notes)
    obs=last.strftime("%Y-%m-%d")

    if request.method == 'POST':
        if request.form['night']: obs = request.form['night']  #selected night

        if 'load' in request.form:
            if request.form['night']: obs=request.form['night']

        elif 'log' in request.form:
            #generate new log after changes and show it
            subprocess.call(["python3", "make_log.py", path0+obs])
            return send_file('logs/'+obs+'_log.pdf', download_name=obs+'_log.pdf', as_attachment=True)

        elif 'save' in request.form:
            for x in request.form:
                if 'fits' in x: notes[x]=request.form[x]
            notes['meteo']=request.form['meteo']
            notes['general']=request.form['general']

            notes1={}
            for x in notes:
                #remove empty notes
                if len(notes[x])>0: notes1[x]=notes[x]
            f=open('notes/'+obs+'.json','w')
            json.dump(notes1,f)
            f.close()
            os.chmod('notes/'+obs+'.json', 0o666)

            saved=True

    #load old notes
    path=path0+obs+'/'
    if os.path.isfile('notes/'+obs+'.json'):
        f=open('notes/'+obs+'.json','r')
        notes=json.load(f)
        f.close()
    else:
        f=open('notes/'+obs+'.json','w')
        json.dump(notes,f)
        f.close()
        os.chmod('notes/'+obs+'.json', 0o666)

    #list all files + split path and name
    files = {x: os.path.splitext(os.path.basename(x))[0] for x in sorted(glob.glob(path+'*.fits'))[::-1]}

    #get snr
    sn={}
    ics={}
    simc={}
    exps={}
    post={}
    for f in files:
        try:
            hdu=fits.open(f)[0]
            header=hdu.header

            if not 'IMAGETYP' in header:
                if 'bias' in f.lower(): sn[f]=''
                elif 'zero' in f.lower(): sn[f]=''
                elif 'flat' in f.lower(): sn[f]=''
                elif 'comp' in f.lower(): sn[f]=''
                elif 'test' in f.lower(): sn[f]=''
                elif 'thar' in f.lower(): sn[f]=''
                elif 'dark' in f.lower(): snr[f]=''
                else: snr[f]=SNR(f,mask='sim-mask.dat')
            elif not header['IMAGETYP'].lower()=='science': snr[f]=''
            else: sn[f]=SNR(f,mask='sim-mask.dat')

            #IC in FE
            if 'FRONTEND_POSITION2' in header:
                if header['FRONTEND_POSITION2']>79000 and header['FRONTEND_POSITION2']<100000: ics[f]='no'
                elif header['FRONTEND_POSITION2']<2000 and header['FRONTEND_POSITION2']>50: ics[f]='yes'
                else: ics[f]='err'
            else: ics[f]=''

            #sim.cal. - CU
            if 'SIMULT' in header:
                #if header['SIMULT']=='THAR_CU': simc[f]='ThAr'
                #elif header['SIMULT']=='I2_CU': simc[f]='IC'
                #elif header['SIMULT']=='OFF' and ('ttarget' in header['OBJECT'] or 'tcomp' in header['OBJECT'] or 'tflat' in header['OBJECT']):
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

                if apfilt2=='FILTER_CLOSED': simc[f]='off'
                else:
                    if ic_lamp and cu_ic and not (comp or flat): simc[f]='IC'
                    elif comp and not (flat or ic_lamp): simc[f]='ThAr'
                    elif flat and not (comp or ic_lamp): simc[f]='flat'
                    elif (not flat) and (not comp) and (not ic_lamp): simc[f]='off'
                    else: simc[f]='err'
                #else: simc[f]='off'
                if compU>tharMax:
                    #broken lamp!
                    simc[f]+='-ThArErr'
            else: simc[f]=''
            
            if 'OBJECT' in header:
                if 'flat' in header['OBJECT'] or 'comp' in header['OBJECT']:
                    if '_' in header['OBJECT']: post[f]=' ('+header['OBJECT'].split('_')[1]+')'
                    else: post[f]=' (all)'
                else: post[f]=''
            else: post[f]=''

            exps[f]=int(round(header['EXPOSURE']))
        except:
            sn[f]=''
            ics[f]=''
            post[f]=''
            exps[f]=''

    return render_template('admin.html',files=files,path=path,notes=notes,night=obs,saved=saved,snr=sn,ic=ics,exp=exps,sim=simc,postfix=post)

def load_limits():
    '''load and process limits'''
    east=np.loadtxt('limits_east.txt')
    west=np.loadtxt('limits_west.txt')
    limits=np.append(east,west[::-1],axis=0)

    i=np.where(np.abs(np.diff(np.sign(limits[:,1]+90)))>0)[0]
    limits1=np.append(limits[:i[0]+1], [[(limits[i[0]+1,0]-limits[i[0],0])/(limits[i[0]+1,1]-limits[i[0],1])*(-90-limits[i[0],1])+limits[i[0],0],-89.99]],axis=0)
    limits1=np.append(limits1, [[(limits[i[0]+1,0]-limits[i[0],0])/(limits[i[0]+1,1]-limits[i[0],1])*(-90-limits[i[0],1])+limits[i[0],0],-90.01]],axis=0)
    limits1=np.append(limits1,limits[i[0]+1:i[1]+1],axis=0)
    limits1=np.append(limits1, [[(limits[i[1]+1,0]-limits[i[1],0])/(limits[i[1]+1,1]-limits[i[1],1])*(-90-limits[i[1],1])+limits[i[1],0],-90.01]],axis=0)
    limits1=np.append(limits1, [[(limits[i[1]+1,0]-limits[i[1],0])/(limits[i[1]+1,1]-limits[i[1],1])*(-90-limits[i[1],1])+limits[i[1],0],-89.99]],axis=0)
    limits1=np.append(limits1,limits[i[1]+1:],axis=0)

    eastLim=limits1[np.where(limits1[:,1]>-90)]
    westLim=limits1[np.where(limits1[:,1]<-90)]

    return eastLim, westLim

eastLim, westLim = load_limits()
PathE=mplPath.Path(eastLim)
PathW=mplPath.Path(westLim)

def sunAlt(date,time,lon,lat,alt=0):
    '''get sun altitude for given location and UTC time'''
    loc=EarthLocation(lon=float(lon)*u.deg, lat=float(lat)*u.deg, height=float(alt)*u.meter)
    dt=Time(date+' '+time)

    sun=get_sun(dt)
    altazCoor=AltAz(location=loc,obstime=dt)

    altaz=sun.transform_to(altazCoor)

    return altaz.alt.degree

def sunRise(date,time,lon,lat,alt=0):
    '''get next astro. twilight and sunrise'''
    #approx. local noon (in UTC)
    dt=Time((Time(date+' '+time)-TimeDelta(14*u.hour)).strftime('%Y-%m-%d')+' '+str(12-int(round(float(lon)/15))).rjust(2,'0')+':00:00')

    sun=get_sun(dt)

    dec=sun.dec.degree

    #sunrise
    ha=np.rad2deg(np.arccos(-np.tan(np.deg2rad(dec))*np.tan(np.deg2rad(float(lat)))))
    sid=360-ha+sun.ra.degree-dt.sidereal_time('mean',float(lon)*u.deg).degree
    if sid>=360: sid-=360

    rise=dt+TimeDelta(sid/15*3600*u.second)

    #astro twilight
    ha=np.rad2deg(np.arccos((np.sin(np.deg2rad(-18))-np.sin(np.deg2rad(dec))*np.sin(np.deg2rad(float(lat))))/(np.cos(np.deg2rad(dec))*np.cos(np.deg2rad(float(lat))))))
    sid=360-ha+sun.ra.degree-dt.sidereal_time('mean',float(lon)*u.deg).degree
    if sid>=360: sid-=360

    astro=dt+TimeDelta(sid/15*3600*u.second)

    return astro, rise


def guiderInfo(name):
    ''''read info from guider header'''
    #fits header -> OCHUM, OCWINDD, OCWINDS, OCTEMP, OCPGM
    info={}
    gc.collect()
    
    try:
        hdu=fits.open(name)[0]
        header=hdu.header
        info['date']=header['DATE-OBS']
        info['time']=header['UT']

        dt,px_x,px_y=fwhm(name)
    except:
        #IO error = file not available (writing?)
        return {}

    if len(px_x)*len(px_y)==0:
        info['fwhm']=np.nan
    else:
        #mean value from all stars
        px_x=np.mean(px_x)
        px_y=np.mean(px_y)

        info['fwhm']=(px_x+px_y)/2*guider_res  #mean value of fwhm in arcsec

    #coordinates and offsets
    info['RA']=header['RA']
    info['DEC']=header['DEC']
    info['user-offset_RA']=header['TELUORA']
    info['user-offset_DEC']=header['TELUODEC']
    info['guider-offset_RA']=header['TELAORA']
    info['guider-offset_DEC']=header['TELAODEC']

    loc=EarthLocation(lon=float(header['LONGITUD'])*u.deg, lat=float(header['LATITUDE'])*u.deg, height=float(header['HEIGHT'])*u.meter)
    dt=Time(info['date']+' '+info['time'])

    altazCoor=AltAz(location=loc,obstime=dt)
    ra='{}h{}m{}s'.format(*info['RA'].replace(':',' ').replace(',','.').split())
    dec='{}d{}m{}s'.format(*info['DEC'].replace(':',' ').replace(',','.').split())
    coord=SkyCoord(ra,dec)

    altaz=coord.transform_to(altazCoor)

    info['alt']=altaz.alt.degree
    info['azm']=altaz.az.degree
    info['airmass']=float(altaz.secz)

    #weather info
    info['temp']=header['OCTEMP']
    info['hum']=header['OCHUM']
    info['wind']=header['OCWINDS']
    info['wind-dir']=header['OCWINDD']
    info['clouds']=header['OCPGM']
    info['press']=header['OCATM']
    info['bright']=header['OCBRTM']

    info['sun']=sunAlt(info['date'],info['time'],header['LONGITUD'],header['LATITUDE'],header['HEIGHT'])

    astro, rise=sunRise(info['date'],info['time'],header['LONGITUD'],header['LATITUDE'],header['HEIGHT'])

    info['astro']=astro.strftime('%H:%M')
    info['astro-dt']=(astro-Time(info['date']+' '+info['time'])).sec/3600
    info['rise']=rise.strftime('%H:%M')
    info['rise-dt']=(rise-Time(info['date']+' '+info['time'])).sec/3600

    if header['TELPOS']==0:
        info['pos']='East'
        limit=eastLim
    else:
        info['pos']='West'
        limit=westLim

    #estimate time to limits
    try:
        ha=float(header['TELHA'])
        da=float(header['TELDA'])
        if header['TELPOS']==0:
            info['ha']=ha
            info['de']=da
            i=np.where((limit[:,0]>ha)*(limit[:,0]>5))[0]    #use only right part of limit
        else:
            info['ha']=ha-180
            info['de']=-180-da
            i=np.where((limit[:,0]>ha)*(limit[:,0]>180))[0]
    except ValueError:
        info['limit']=-1
        return info

    j=np.argmin(np.abs(limit[i,1]-da))
    try:
        f = interpolate.interp1d(limit[i,1],limit[i,0])
        info['limit']=float((f(da)-ha)/15)
    except: info['limit']=(limit[i[j],0]-ha)/15

    gc.collect()
    return info

history=[] #store old conditions values
olddate=''
lastname=''

@app.route('/conditions', methods=['GET', 'POST'])
def conditions():
    '''show current weather and obs. conditions -> based on guider image'''
    global history,olddate,lastname
    gc.collect()
    
    try:
        #date -> from folder name
        if len(glob.glob(path0+'20*/'))>0:
            path=sorted(glob.glob(path0+'20*/'))[-1]
            obs=path.strip().split('/')[-2]
        else: obs='2024-01-01'

        if not obs==olddate:
            #reset after new night = new folder
            olddate=obs
            history=[]

        last=datetime.datetime.strptime(obs,"%Y-%m-%d")

        date_guider=last#-datetime.timedelta(days = 1)

        path=guider+date_guider.strftime("%Y/%Y-%m-%d/")
        if not os.path.isdir(path): path=guider0

        files=glob.glob(path+'y'+date_guider.strftime("%Y%m%d")+'*.fit')
        #files=glob.glob('guider/*.fit')

        if len(files)==0:
            condi={}
            plots={}
        else:
            condi={}
            name=sorted(files)[-1]
            if not lastname==name:
                condi=guiderInfo(name)
                if len(condi)>0:
                    history.append(dict(condi))
                    lastname=name
                elif len(files)>1:
                    #try previous file
                    name=sorted(files)[-2]
                    if not lastname==name:
                        condi=guiderInfo(name)
                        if len(condi)>0:
                            history.append(dict(condi))
                            lastname=name

            if len(history)>0:
                condi=dict(history[-1])

            # history=[]
            # for name in sorted(files):
            #     condi=guiderInfo(name)
            #     history.append(dict(condi))

            plots={}
            if len(history)>1:
                plots['dt']=[x['date']+' '+x['time'] for x in history]
                plots['temp']=[x['temp'] for x in history]
                plots['hum']=[x['hum'] for x in history]
                plots['wind']=[x['wind'] for x in history]
                plots['wind-dir']=[x['wind-dir'] for x in history]
                plots['wind']=[x['wind'] for x in history]
                plots['clouds']=[x['clouds'] for x in history]
                plots['press']=[x['press'] for x in history]
                plots['bright']=[x['bright']/1000 for x in history]
                plots['fwhm']=[]
                plots['dtF']=[]

                for x in history:
                    if not np.isnan(x['fwhm']):
                        plots['fwhm'].append(x['fwhm'])
                        plots['dtF'].append(x['date']+' '+x['time'])


                #calculate guider movements
                ra0=history[0]['guider-offset_RA']
                dec0=history[0]['guider-offset_DEC']
                plots['guider-RA']=[]
                plots['guider-DEC']=[]
                plots['dtG']=[]

                for x in history[1:]:
                    ra=x['guider-offset_RA']
                    dec=x['guider-offset_DEC']

                    dra=ra-ra0
                    ddec=dec-dec0

                    if abs(dra)<50 and abs(ddec)<50:
                        plots['guider-RA'].append(dra)
                        plots['guider-DEC'].append(ddec)
                        plots['dtG'].append(x['date']+' '+x['time'])
                    ra0=ra
                    dec0=dec
    except:
        condi={}
        plots={}

    #detect if running on localhost -> speed-up loading
    if 'localhost' in request.headers.get('Host'): local=True
    else: local=False

    return render_template('conditions.html',condi=condi,plots=plots,local=local)

def plotLim(ha,dec):
    '''plot east/west telescope limits from hour angle and dec'''
    if ha<-90: ha+=360
    if ha>270: ha-=360

    haW=ha+180
    if haW>270: haW-=360
    decW=-180-dec

    fig=plt.figure()
    ax1 = fig.add_subplot(111)
    ax1.plot(eastLim[:,0],eastLim[:,1],'b-')
    ax1.plot(westLim[:,0],westLim[:,1],'r-')
    ax1.plot(ha,dec,'bo')
    ax1.plot(haW,decW,'ro')
    ax1.set_xlim(-90,270)
    ax1.set_ylim(-240,60)
    ax1.hlines(-90, -90, 270, colors='k',linestyles=':')

    ax1.xaxis.set_ticks(range(-90,270+1,30),[str(int(round(i/15))) for i in range(-90-180,270-180+1,30)])
    ax1.set_xlabel('West position - Hour angle (hours)')

    ax2 = ax1.twiny()
    ax2.set_xlim(-90,270)
    ax2.xaxis.set_ticks(range(-90,270+1,30),[str(int(round(i/15))) for i in range(-90,270+1,30)])
    ax2.set_xlabel('East position - Hour angle (hours)')

    ax1.yaxis.set_ticks(range(-240,60+1,30),[str(i) if i>=-90 else str(-i-180) for i in range(-240,60+1,30)])
    ax1.set_ylabel('Declination (deg)')
    ax1.text(220, -70, 'east', color='blue')
    ax1.text(220, -110, 'west', color='red')
    plt.tight_layout()

    buf=io.BytesIO()
    plt.savefig(buf,format='png',dpi=150)
    plt.close()
    buf.seek(0)
    #load result from buffer to html output
    plot = base64.b64encode(buf.getvalue()).decode('utf8')
    buf.close()

    return plot

@app.route("/plot_limits", methods=['GET'])
def plot_limits():
    '''plot east/west telescope limits from hour angle and dec'''
    try:
        ha=float(request.args.get('ha'))
        dec=float(request.args.get('dec'))
    except TypeError:
        return 'Incorrect format of input parameters!'

    return render_template('image.html',image=plotLim(ha,dec))


@app.route('/limits',methods=['GET','POST'])
def limits():
    if request.method == 'POST':
        date=request.form['date']
        time=request.form['time']

        sign = lambda x: -1 if x < 0 else 1
        ra=[float(x) for x in request.form['ra'].replace(':',' ').split()]
        ra=sign(ra[0])*(abs(ra[0])+ra[1]/60+ra[2]/3600)*15

        dec=[float(x) for x in request.form['dec'].replace(':',' ').split()]
        dec=sign(dec[0])*(abs(dec[0])+dec[1]/60+dec[2]/3600)

        dt=Time(date+' '+time)

        lst=dt.sidereal_time('mean',obs_lon*u.deg).degree

        ha=(lst-ra)%(360)

        if ha<-90: ha+=360
        if ha>270: ha-=360

        haW=ha+180
        if haW>270: haW-=360
        decW=-180-dec

        if PathE.contains_point((ha,dec)):
            i=np.where((eastLim[:,0]>ha)*(eastLim[:,0]>5))[0]       #use only right part of limit
            j=np.argmin(np.abs(eastLim[i,1]-dec))
            try:
                f = interpolate.interp1d(eastLim[i,1],eastLim[i,0])
                east=float((f(dec)-ha)/15)
            except: east=(eastLim[i[j],0]-ha)/15
        else: east=0

        if PathW.contains_point((haW,decW)):
            i=np.where((westLim[:,0]>haW)*(westLim[:,0]>180))[0]   #use only right part of limit
            j=np.argmin(np.abs(westLim[i,1]-decW))
            try:
                f = interpolate.interp1d(westLim[i,1],westLim[i,0])
                west=float((f(decW)-haW)/15)
            except: west=(westLim[i[j],0]-haW)/15
        else: west=0

        return render_template('limits.html',ra=request.form['ra'],dec=request.form['dec'],date=date,time=time,plot=plotLim(ha,dec),east=east,west=west)

    return render_template('limits.html',ra='',dec='',date='',time='')


if __name__ == '__main__':
   app.run('0.0.0.0',5000)
