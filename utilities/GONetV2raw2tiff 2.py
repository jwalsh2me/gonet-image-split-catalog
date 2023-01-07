#!/usr/bin/env python
# from ast import arg
import numpy as np
# from libtiff import TIFF
from tifffile import tifffile
from datetime import datetime
import sys
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

### TEST VARS

# source_camera = '206'
td = datetime.today().strftime('%Y-%m-%d')

#* Function's Start
def get_exif(filename):
    image = Image.open(filename)
    image.verify()
    return image._getexif()  # type: ignore

def get_labeled_exif(exif):
    labeled = {}
    # labeled['image_name'] = image_name
    for (key, val) in exif.items():
        labeled[TAGS.get(key)] = val
    return labeled

def get_geotagging(exif):
    if not exif:
        raise ValueError("No EXIF metadata found")

    geotagging = {}
    for (idx, tag) in TAGS.items():
        if tag == 'GPSInfo':
            if idx not in exif:
                raise ValueError("No EXIF geotagging found")

            for (key, val) in GPSTAGS.items():
                # print(key, val) #debug
                if key in exif[idx]:
                    geotagging[val] = exif[idx][key]

    return geotagging

def get_decimal_from_dms(dms, ref):
    # Convert DMS to decimal degrees

    degrees = dms[0]
    minutes = dms[1] / 60.0
    seconds = dms[2] / 3600.0

    if ref in ['S', 'W']:
        degrees = -degrees
        minutes = -minutes
        seconds = -seconds

    return round(degrees + minutes + seconds, 5)


def get_coordinates(geotags):
    lat = get_decimal_from_dms(
        geotags['GPSLatitude'], geotags['GPSLatitudeRef'])
    lon = get_decimal_from_dms(
        geotags['GPSLongitude'], geotags['GPSLongitudeRef'])
    return (lat, lon)

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
sp[:,:,2]=s[0::2,0::2]                      # blue
sp = np.multiply(sp,16) ## adjusting the image to be saturated correctly(it was imported from 12bit into a 16bit) so it is a factor of 16 dimmer than should be, i.e this conversion

sp=sp.transpose()


# now we need to write it to a tiff file
array = ((sp+0.5).astype('uint16'))
tifffile.imwrite(imageOutFileName, array, photometric='rgb')
# tiff = TIFF.open(imageOutFileName, mode='w')
# tiff.write_image((sp+0.5).astype('uint16'),write_rgb=True) # the +0.5 rounds the green channel
# tiff.close()

exif = get_exif(arglist[1])

# print(f"EXIF data :: {exif}")
# for item in exif:
#     print(item)
# print("---- End EXIF ------------------------------------")

if not exif:
    labeled = {}
    labeled['Software'] = f'{source_camera} UNK_VER WB: UNK, UNK'
    geotags = 'UNK'
    labeled['NoEXIF'] = True
else:
    labeled = get_labeled_exif(exif)
    if 'Software' not in labeled:
        print("No Software")
        labeled['Software'] = f'{source_camera} UNK_VER WB: UNK, UNK'
    image_date = str(labeled["DateTimeOriginal"]).split(' ')[0].replace(':', '-')
    image_time = str(labeled["DateTimeOriginal"]).split(' ')[1]
    labeled['image_time'] = image_time
    labeled['image_date'] = image_date

    gonet_software_version = str(labeled["Software"]).split(' ')[1]
    print(gonet_software_version)
    has_artist = float(gonet_software_version) >= 21
    if has_artist:
        print("Has Artist")
        artist_lat = str(labeled["Artist"]).split(' ')[8]
        artist_lon = str(labeled["Artist"]).split(' ')[10].rstrip(',')
        labeled['lat_lon'] = f"{artist_lat} {artist_lon}"
        labeled['altitude'] = str(labeled["Artist"]).split(' ')[12]
    else:
    #* remove EXIF lat-lon
        geotags = get_geotagging(exif)
        if geotags == 'UNK':
            pass
        else:
            lat_lon = get_coordinates(geotags)
            labeled['lat_lon'] = f"{lat_lon[0]}, {lat_lon[1]}"
            labeled['altitude'] = (geotags['GPSAltitude'])

# format GONet Custom EXIF
gonet_camera_name = str(labeled["Software"]).split(' ')[0]
# gonet_camera_name = str(labeled["Artist"]).split(' ')[1]
gonet_software_version = str(labeled["Software"]).split(' ')[1]
# has_artist = float(gonet_software_version) > 20

gonet_white_balance = str(labeled["Software"]).split(
    ' ')[3] + str(labeled["Software"]).split(' ')[4]


# artist_tag = labeled["Artist"]
# artist_version = str(labeled["Artist"]).split(' ')[3].rstrip(',')
# artist_lat = str(labeled["Artist"]).split(' ')[8]
# artist_lon = str(labeled["Artist"]).split(' ')[10].rstrip(',')
# artist_alt = str(labeled["Artist"]).split(' ')[12]
# print(f"Geotags:: {geotags}")

image_name = 'output.jpeg'


ddb_dict = {}
ddb_dict['image_name'] = image_name
ddb_dict['gonet_camera_name'] = gonet_camera_name
ddb_dict['gonet_software_version'] = gonet_software_version
ddb_dict['gonet_white_balance'] = gonet_white_balance
ddb_dict['source_location'] = "source_uri"
ddb_dict['tiff_location'] = "tiff_uri"
ddb_dict['jpeg_location'] = "jpeg_uri"
ddb_dict['lat_lon'] = labeled['lat_lon']
for key, val in labeled.items():
    if key not in ('GPSInfo', 'Artist', 'Software', 'ComponentsConfiguration', 'ExifVersion', 'WhiteBalance', 'MakerNote'):
        # print(f"Not in labeled: {key} :: {val}")
        ddb_dict[key] = str(val)
ddb_dict['item_added'] = td
for key, val in ddb_dict.items():
    print(f"{key} = {val}")



#     ddb_dict['item_added'] = td
#     table.put_item(Item=ddb_dict)
#     print(f"Added Item to DynamoDB Table - {Envs.ddb_table} :: {ddb_dict}")
# except botocore.exceptions.ClientError as e:
#     print(f"ERROR! - {e}")
# # print(f"Added Item to DynamoDB Table - {Envs.ddb_table} :: {ddb_dict}")
# ## cleanup /tmp
# print("Cleaning up /tmp")
# os.remove(source_image_tmp)
# os.remove(f"/tmp/{tiff_filename}")
# os.remove(f"/tmp/{jpeg_filename}")
# print('## DONE')

print(arglist)

jpeg = Image.open(arglist[1]).convert("RGB")
exif = jpeg.info['exif']
print('EXIF saved on JPEG')
jpeg.save(("split-jpeg.jpeg"), 'JPEG', exif=exif)

if has_artist:
    print('Has Artist')
# print(artist_tag)
# print(artist_version)
# print(f"{artist_lat} {artist_lon}")
