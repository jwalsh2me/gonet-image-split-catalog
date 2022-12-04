#!/usr/bin/env python
import numpy as np
# from libtiff import TIFF
from tifffile import tifffile
import sys

arglist=sys.argv

imageInFileName=arglist[1]
imageOutFileName=imageInFileName.rsplit('.',1)[0]+'.tif'

file = open(imageInFileName, "rb")
rawFileOffset = 18711040
rawHeaderSize = 32768
rawDataOffset = rawFileOffset - rawHeaderSize
RELATIVETOEND = 2

file.seek(-rawDataOffset,RELATIVETOEND)
pixelsPerLine=4056
pixelsPerColumn=3040
usedLineBytes=int(pixelsPerLine*12/8)

s=np.zeros((pixelsPerLine,pixelsPerColumn),dtype='uint16')
# do this at least 3040 times though the precise number of lines is a bit unclear
for i in range(pixelsPerColumn):
    # read in 6112 bytes, but only 6084 will be used
    bdLine = file.read(6112)
    gg=np.array(list(bdLine[0:usedLineBytes]),dtype='uint16')
    s[0::2,i] = (gg[0::3]<<4) + (gg[2::3]&15)
    s[1::2,i] = (gg[1::3]<<4) + (gg[2::3]>>4)

# form superpixel array
sp=np.zeros((int(pixelsPerLine/2),int(pixelsPerColumn/2),3),dtype='uint16')
sp[:,:,0]=s[1::2,1::2]                      # red
sp[:,:,1]=(s[0::2,1::2]+s[1::2,0::2])/2     # green
sp[:,:,2]=s[0::2,0::2]                      # bluepython

sp=sp.transpose()


# now we need to write it to a tiff file
array = ((sp+0.5).astype('uint16'))
tifffile.imwrite(imageOutFileName, array, photometric='rgb')
# tiff = TIFF.open(imageOutFileName, mode='w')
# tiff.write_image((sp+0.5).astype('uint16'),write_rgb=True) # the +0.5 rounds the green channel
# tiff.close()
