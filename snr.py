import sys
from astropy.io import fits
import numpy as np

def SNR(name,signal=False,points=50,offset=0,mask=''):
    '''estimate SNR of echelle spectrum
    signal - return also signal and background level
    points - number of points in one bin for bg
    offset - offset of center line (sim.cal. - avoid ThAr lines)
    mask - name of file with mask for sim. ThAr (ignore px in file)
    '''
    image = fits.getdata(name).astype('float')

    #denoise ?
    #image=median_filter(image,np.ones((3, 3)))

    shape=image.shape
    #image center
    yC=int(shape[0]/2)
    xC=int(shape[1]/2)

    #center row
    center=image[yC+offset,:]

    if len(mask)>0:
        i=np.loadtxt(mask,dtype=int)[:,0]
        mask=np.zeros(len(center))
        mask[i]=1
        center=np.ma.masked_array(center,mask=mask).filled(np.nan)

    if points==0:
        bg=np.nanpercentile(center,25)#+2
        #bg=np.mean(center[center<np.percentile(center,50)])

        #mse = (center-bg)**2
        #mse[center<bg]=0
        #snr = 10*np.log10(np.mean(mse))
        snr=np.sqrt(np.nanpercentile(center-bg,99))

        if signal: return snr, center, bg
        else: return snr

    bgs=[]
    for i in range(0,len(center)-points,points):
        values = center[i:i+points]

        #estimate background level
        #bg=np.median(values[values<np.percentile(values,80)])
        bg=np.nanpercentile(values,25)
        bgs.append(bg)

    if len(center)-i>points/2:
        #end of frame
        values = center[i+points:]

        #estimate background level
        #bg=np.median(values[values<np.percentile(values,80)])
        bg=np.nanpercentile(values,25)
        bgs.append(bg)

    #interpolate background for whole data
    bg=np.interp(list(range(len(center))),list(range(0,len(bgs)*points,points)),bgs)

    snr=np.sqrt(np.nanpercentile(center-bg,99))

    if signal: return np.mean(snr), center, bg
    else: return np.mean(snr)


if __name__ == "__main__":
    import matplotlib.pyplot as mpl

    name=sys.argv[1]
    points=50
    offset=0
    mask='sim-mask.dat'

    snr,center,bg=SNR(name,signal=True,points=points,offset=offset,mask=mask)

    #np.savetxt('flat-sim.dat',np.column_stack((list(range(len(center))),center)),fmt=['%d','%d'],delimiter='    ',header='px     value')

    print(snr)

    mpl.figure()
    mpl.plot(center)
    mpl.xlabel('pixel')
    mpl.ylabel('intensity value')
    if points>0: mpl.plot(bg)
    else: mpl.hlines(bg,xmin=0,xmax=len(center),colors='red')

    image=fits.getdata(name).astype('float')
    shape=image.shape
    yC=int(shape[0]/2)+offset

    fig, ax = mpl.subplots(1, 1)
    ax.imshow(image, cmap=mpl.cm.gray, origin='lower',aspect='equal',norm='linear',vmax=np.nanpercentile(center,99))
    ax.hlines(yC,xmin=0,xmax=shape[1],colors='red')
    ax.set_xlim(0,shape[1])
    ax.set_ylim(0,shape[0])

    mpl.show()
