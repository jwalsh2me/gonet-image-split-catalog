import os
import boto3
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import numpy as np
import picamraw
from tifffile import tifffile
# import exifread
from picamraw import PiRawBayer, PiCameraVersion


class Envs:

    # Lambda Env Vars from SAM Template
    source_bucket = os.environ['source_bucket']
    tiff_bucket = os.environ['tiff_bucket']
    jpeg_bucket = os.environ['jpeg_bucket']

s3 = boto3.client("s3")

#ToDo Add DDB Function


def lambda_handler(event, context):
    print('## EVENT')
    print(event)
    s3_key = event["Records"][0]["s3"]["object"]["key"]
    s3_bucket = event["Records"][0]["s3"]["bucket"]["name"]
    source_image_tmp = (f"/tmp/{s3_key.split('/')[1]}")
    tiff_filename = (f"{s3_key.split('/')[1].split('.')[0]}.tiff")
    jpeg_filename = (f"{s3_key.split('/')[1].split('.')[0]}.jpeg")
    source_camera = s3_key.split('/')[0]
    print('## ENV')
    print(f"Source Bucket: {s3_bucket}")
    print(f"Source Key: {s3_key}")
    print(f"Camera Name: {source_camera}")
    print(f"TIFF Output Filename: {tiff_filename}")
    print(f"JPEG Output Filename: {jpeg_filename}")

    s3.download_file(s3_bucket, s3_key, source_image_tmp)
    # Split off the TIFF
    source_image = picamraw.PiRawBayer(
        filepath=source_image_tmp,  camera_version=picamraw.PiCameraVersion.V1, sensor_mode=0)
    c = source_image.to_rgb()
    #! Keep the RGB as the split tiff

    # c = source_image.bayer_array   # A 16-bit 2D numpy array of the bayer data
    # c = source_image.bayer_order   # A `BayerOrder` enum that describes the arrangement of the R,G,G,B pixels in the bayer_array
    # c = source_image.to_rgb()      # A 16-bit 3D numpy array of bayer data collapsed into RGB channels (see docstring for details).
    # c = source_image.to_3d()       # A 16-bit 3D numpy array of bayer data split into RGB channels (see docstring for details).

    array = (64*c.astype(np.uint16))
    tifffile.imwrite((f"/tmp/{tiff_filename}"), array, photometric='rgb')

    s3.upload_file((f"/tmp/{tiff_filename}"), Envs.tiff_bucket, (f"{source_camera}/{tiff_filename}"))

    print('TIFF Uploaded')
    # Splitting off the JPEG, saving and applying EXIF from source to JPEG
    jpeg = Image.open(source_image_tmp).convert("RGB")
    exif = jpeg.info['exif']
    print('EXIF saved')
    jpeg.save((f"/tmp/{jpeg_filename}"), 'JPEG', exif=exif)
    s3.upload_file((f"/tmp/{jpeg_filename}"), Envs.jpeg_bucket, (f"{source_camera}/{jpeg_filename}"))
    # Return Exif tags
    exif_dict = {}
    with open(((f"/tmp/{jpeg_filename}")), 'rb') as jpeg_exif:
        tags = exifread.process_file(jpeg_exif, details = False)
        for key, value in tags.items():
            exif_dict[key.split(' ')[1]] = value

        filename = jpeg_filename
        camera = str(exif_dict["Software"]).split(' ')[0]
        software_version = str(exif_dict["Software"]).split(' ')[1]
        white_balance = str(exif_dict["Software"]).split(' ')[3] + str(exif_dict["Software"]).split(' ')[4]
        altitude = str(exif_dict["GPSAltitude"])
        lat = str(exif_dict["GPSLatitude"])
        lat_ref = str(exif_dict["GPSLatitudeRef"])
        long = str(exif_dict["GPSLongitude"])
        long_ref = str(exif_dict["GPSLongitudeRef"])
        aperture = str(exif_dict["ApertureValue"])
        exposure = str(exif_dict["ShutterSpeedValue"])
        date = str(exif_dict["DateTimeOriginal"]).split(' ')[0].replace(':','-')
        time = str(exif_dict["DateTimeOriginal"]).split(' ')[1]
    print(filename)
    print(camera, software_version)
    print(date, time)
    print(aperture)
    print(exposure)
    print(white_balance)
    # dir_list = os.listdir('/tmp/')
    # print(dir_list)
    s3.upload_file((f"/tmp/{jpeg_filename}"), Envs.jpeg_bucket, (f"{source_camera}/{jpeg_filename}"))

    print('### DONE ###')

