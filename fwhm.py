from astropy.io import fits
import numpy as np
#import matplotlib.pyplot as mpl
from scipy.optimize import curve_fit
from skimage.feature import peak_local_max
from skimage.filters import median as median_filter
import sys

#hole=5

def gauss(x,amp,x0,sigma,offset):
    '''1D gaussian'''
    return amp*np.exp(-(x-x0)**2/(2*sigma**2))+offset

def gauss2D(xy,amp,x0,y0,sigma_x,sigma_y,offset):
    '''2D asymetric gaussian'''
    x, y = xy
    return (amp*(np.exp(-(x-x0)**2/(2*sigma_x**2))*np.exp(-(y-y0)**2/(2*sigma_y**2)))+offset).ravel()

def fwhm(name):
    '''measure fwhm of stars in image'''
    hdu=fits.open(name)[0]
    header=hdu.header
    date=header['DATE-OBS']
    time=header['UT']
    #TODO! datetime/jd...?

    image = fits.getdata(name).astype('float')

    #denoise
    image=median_filter(image,np.ones((3, 3)))

    #size of 1star subframe
    size=30
    x=np.arange(-size,size,1)
    x,y=np.meshgrid(x,x)

    bg=np.median(image)   #background level
    p0=[1000,0,0,5,5,bg]   #initial values of params

    fwhm_x=[]
    fwhm_y=[]

    shape=image.shape
    #image center
    yC=int(shape[0]/2)
    xC=int(shape[1]/2)

    #find peaks=stars on image
    peaks=peak_local_max(image,num_peaks=10,min_distance=10,threshold_abs=bg+50,exclude_border=size)   #,threshold_rel=0.15

    fwhm_x0=[]
    fwhm_y0=[]
    for star in peaks:
        #coordinates
        x0=int(star[1])
        y0=int(star[0])

        try: popt,pcov=curve_fit(gauss2D,(x,y),image[y0-size:y0+size,x0-size:x0+size].ravel(),p0=p0)  #fit on subimage
        except (RuntimeError, ValueError):
            #fit not successsful...
            # fig, ax = mpl.subplots(1, 1)
            # ax.imshow(image[y0-size:y0+size,x0-size:x0+size], cmap=mpl.cm.jet, origin='lower',extent=(-size,size,-size,size))
            # mpl.show()
            continue

        #calculate fwhm from sigma
        fwhm_x1=2*np.sqrt(2*np.log(2))*abs(popt[3])
        fwhm_y1=2*np.sqrt(2*np.log(2))*abs(popt[4])

        if fwhm_x1>2 and fwhm_y1>2 and  fwhm_x1<100 and fwhm_y1<100 and np.isfinite(fwhm_x1) and np.isfinite(fwhm_y1):   #remove hot pixels! and bad values
            if (xC-x0)**2+(yC-y0)**2<size**2:  #on the fiber = hole!
                fwhm_x0.append(fwhm_x1)
                fwhm_y0.append(fwhm_y1)
            else:
                fwhm_x.append(fwhm_x1)
                fwhm_y.append(fwhm_y1)

        # fig, ax = mpl.subplots(1, 1)
        # ax.imshow(image[y0-size:y0+size,x0-size:x0+size], cmap=mpl.cm.jet, origin='lower',extent=(-size,size,-size,size))
        # ax.contour(x, y, gauss2D((x,y),*popt).reshape(2*size,2*size), 10, colors='w')
        # mpl.show()

    #res=0.134
    if len(fwhm_x)>0: return date+' '+time,fwhm_x,fwhm_y   #except of star on fiber
    else: return date+' '+time,fwhm_x0,fwhm_y0   #only star on fiber


if __name__ == "__main__":
    name=sys.argv[1]
    res=float(sys.argv[2])
    dt,fwhm_x,fwhm_y=fwhm(name)
    print(dt,np.mean(fwhm_x),np.mean(fwhm_y),np.mean(fwhm_x)*res,np.mean(fwhm_y)*res)
