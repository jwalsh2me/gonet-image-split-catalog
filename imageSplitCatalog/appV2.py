import os
import botocore
import boto3
from tifffile import tifffile
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import numpy as np


class Envs:

    # Lambda Env Vars from SAM Template
    source_bucket = os.environ['source_bucket']
    tiff_bucket = os.environ['tiff_bucket']
    jpeg_bucket = os.environ['jpeg_bucket']
    ddb_table = os.environ['ddb_table']


td = datetime.today().strftime('%Y-%m-%d')
s3 = boto3.client("s3")
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(Envs.ddb_table)


def get_exif(filename):
    with Image.open(filename) as image:
        image.verify()
        return image._getexif()


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


def lambda_handler(event, context):
    print('#### START - Event Received ####')
    print(event)
    s3_key = event["Records"][0]["s3"]["object"]["key"]
    s3_bucket = event["Records"][0]["s3"]["bucket"]["name"]
    source_image_tmp = (f"/tmp/{s3_key.split('/')[1]}")
    image_name = (f"{s3_key.split('/')[1].split('.')[0]}")
    tiff_filename = (f"{s3_key.split('/')[1].split('.')[0]}.tiff")
    jpeg_filename = (f"{s3_key.split('/')[1].split('.')[0]}.jpeg")
    source_camera = s3_key.split('/')[0]
    source_uri = (f"s3://{s3_bucket}/{s3_key}")
    tiff_uri = (f"s3://{Envs.tiff_bucket}/{source_camera}/{tiff_filename}")
    jpeg_uri = (f"s3://{Envs.jpeg_bucket}/{source_camera}/{jpeg_filename}")
    print('## ENV VALUES ##')
    print(f"Source Bucket: {s3_bucket}")
    print(f"Source Key: {s3_key}")
    print(f"Image Name: {image_name}")
    print(f"Camera Name: {source_camera}")
    print(f"Source Location: {source_uri}")
    print(f"TIFF Output Filename: {tiff_filename}")
    print(f"TIFF Location: {tiff_uri}")
    print(f"JPEG Output Filename: {jpeg_filename}")
    print(f"JPEG Location: {jpeg_uri}")
    print(f"DynamoDB Table: {Envs.ddb_table}")

    print(f"## Image Processing ##")
    s3.download_file(s3_bucket, s3_key, source_image_tmp)
    # Split off the TIFF
    source_image = open(source_image_tmp, "rb")
    rawFileOffset = 18711040
    rawHeaderSize = 32768
    rawDataOffset = rawFileOffset - rawHeaderSize
    RELATIVETOEND = 2

    source_image.seek(-rawDataOffset, RELATIVETOEND)
    pixelsPerLine = 4056
    pixelsPerColumn = 3040
    # source_image = picamraw.PiRawBayer(
    usedLineBytes = int(pixelsPerLine*12/8)
    s = np.zeros((pixelsPerLine, pixelsPerColumn), dtype='uint16')
    # do this at least 3040 times though the precise number of lines is a bit unclear
    for i in range(pixelsPerColumn):
        # read in 6112 bytes, but only 6084 will be used
        bdLine = source_image.read(6112)
        gg = np.array(list(bdLine[0:usedLineBytes]), dtype='uint16')
        s[0::2, i] = (gg[0::3] << 4) + (gg[2::3] & 15)
        s[1::2, i] = (gg[1::3] << 4) + (gg[2::3] >> 4)
    # form superpixel.tiff-pixel array
    sp = np.zeros(
        (int(pixelsPerLine/2), int(pixelsPerColumn/2), 3), dtype='uint16')
    sp[:, :, 0] = s[1::2, 1::2]                      # red
    sp[:, :, 1] = (s[0::2, 1::2]+s[1::2, 0::2])/2     # green
    sp[:, :, 2] = s[0::2, 0::2]                      # blue
    # adjusting the image to be saturated correctly(it was imported from 12bit into a 16bit) so it is a factor of 16 dimmer than should be, i.e this conversion
    sp = np.multiply(sp, 16)
    sp = sp.transpose()
    array = ((sp+0.5).astype('uint16'))

    tifffile.imwrite((f"/tmp/{tiff_filename}"), array, photometric='rgb')
    s3.upload_file((f"/tmp/{tiff_filename}"), Envs.tiff_bucket,
                   (f"{source_camera}/{tiff_filename}"))
    print('TIFF Uploaded')
    source_image.close()
    # Split off the JPEG, save and apply EXIF from source to JPEG
    jpeg = Image.open(source_image_tmp).convert("RGB")
    exif = jpeg.info['exif']
    print('EXIF saved on JPEG')
    jpeg.save((f"/tmp/{jpeg_filename}"), 'JPEG', exif=exif)
    s3.upload_file((f"/tmp/{jpeg_filename}"), Envs.jpeg_bucket,
                   (f"{source_camera}/{jpeg_filename}"))
    print('JPEG Uploaded')

    # Return Exif tags
    exif = get_exif(source_image_tmp)
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
        image_date = str(labeled["DateTimeOriginal"]).split(' ')[
            0].replace(':', '-')
        image_time = str(labeled["DateTimeOriginal"]).split(' ')[1]
        labeled['image_time'] = image_time
        labeled['image_date'] = image_date
        gonet_software_version = str(labeled["Software"]).split(' ')[1]
        print(f"GONet Software Version: {gonet_software_version}")
        has_artist = float(gonet_software_version) >= 21
        # * V21 software added Artist Tag
        if has_artist:
            print("Has Artist EXIF Tag")
            artist_lat = str(labeled["Artist"]).split(' ')[8]
            artist_lon = str(labeled["Artist"]).split(' ')[10].rstrip(',')
            labeled['lat_lon'] = f"{artist_lat} {artist_lon}"
            labeled['altitude'] = str(labeled["Artist"]).split(' ')[12]
        else:  # decode the GEOtags to get Alt and Lat-Lon
            geotags = get_geotagging(exif)
            if geotags == 'UNK':
                pass
            else:
                lat_lon = get_coordinates(geotags)
                labeled['lat_lon'] = f"{lat_lon[0]}, {lat_lon[1]}"
                labeled['altitude'] = (geotags['GPSAltitude'])

    # * format GONet Custom EXIF
    gonet_camera_name = str(labeled["Software"]).split(' ')[0]
    gonet_software_version = str(labeled["Software"]).split(' ')[1]
    gonet_white_balance = str(labeled["Software"]).split(
        ' ')[3] + str(labeled["Software"]).split(' ')[4]
    has_artist = float(gonet_software_version) > 20

    try:
        ddb_dict = {}
        ddb_dict['image_name'] = image_name
        ddb_dict['gonet_camera_name'] = gonet_camera_name
        ddb_dict['gonet_software_version'] = gonet_software_version
        ddb_dict['gonet_white_balance'] = gonet_white_balance
        ddb_dict['source_location'] = source_uri
        ddb_dict['tiff_location'] = tiff_uri
        ddb_dict['jpeg_location'] = jpeg_uri
        for key, val in labeled.items():
            if key not in ('Software', 'ComponentsConfiguration', 'ExifVersion', 'WhiteBalance', 'MakerNote'):
                # print(f"{key} :: {val}")
                ddb_dict[key] = str(val)
        ddb_dict['item_added'] = td
        table.put_item(Item=ddb_dict)
        # print(f"Added Item to DynamoDB Table - {Envs.ddb_table} :: {ddb_dict}")
    except botocore.exceptions.ClientError as e:
        print(f"ERROR! - {e}")
    print(f"EXIF data added to DDB Table: {Envs.ddb_table}")
    # * cleanup /tmp
    print("Cleaning up /tmp")
    os.remove(source_image_tmp)
    os.remove(f"/tmp/{tiff_filename}")
    os.remove(f"/tmp/{jpeg_filename}")
    print('#### DONE ####')
