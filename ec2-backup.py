import boto3
import json
import datetime
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("-k", "--retention", type=int,
                    help="How many days to keep backups")
parser.add_argument("-p", "--awsprofile",  type=str,
                    help="aws profile.")
parser.add_argument("-i", "--backupid", type=str,
                    help="the nickname of the backup")
parser.add_argument("-r", "--region", type=str,
                    help="aws region")
args = parser.parse_args()

if args.retention:
    retention = args.retention
else:
    retention = 7

if args.awsprofile:
    awsprofile = args.awsprofile
else:
    awsprofile = "default"

if args.backupid:
    backupid = args.backupid
else:
    backupid = "backupcat"

if args.region:
    region = args.region
else:
    region = "us-east-2"



def datetime_handler(x):
    if isinstance(x, datetime.datetime):
        return x.isoformat()
    raise TypeError("Unknown type")

curdate = datetime.datetime.today()
retention = datetime.timedelta(days=retention)

session = boto3.Session(profile_name=awsprofile, region_name=region)

ec2 = session.client('ec2')

result = ec2.describe_instances()

instances = {}
imagestodelete = []
snapshotstodelete = []

print json.dumps(result,default=datetime_handler)
def getInventory():
    for instance in result['Reservations'][0]['Instances']:
        instanceid = instance['InstanceId']
        instances[instanceid] = {}
        instances[instanceid]['tags'] = instance['Tags']
        for tag in instance['Tags']:
            if tag['Key'] == "Name":
                instancename = tag["Value"]
                instances[instanceid]['name'] = instancename

        if instancename:
            imagename = "-".join([instancename, instanceid, backupid, curdate.strftime("%Y%m%d")])
        else:
            imagename = "-".join([instanceid, backupid, curdate.strftime("%Y%m%d")])

        print imagename
        instances[instanceid]['imagename'] = imagename



def createBackup():
    for instance in instances:
        print instances[instance]['name']
        result = ec2.create_image(InstanceId=instance, Name=instances[instance]["imagename"], Description=instances[instance]["imagename"], NoReboot=True)
        imageid = result['ImageId']
        if imageid is None:
            print "Imageid for " + instance + " was not created successfully"

        resources=[imageid]

        result = ec2.describe_images(ImageIds=[imageid])
        for blockdevice in result["Images"][0]["BlockDeviceMappings"]:
            if blockdevice["Ebs"]:
                snapshot = blockdevice["Ebs"]["SnapshotId"]
                resources.append(snapshot)

        print resources

        response = ec2.create_tags(Resources=resources, Tags=instances[instance]['tags'])

        print imageid

def removeOld():
    datetodelete = (curdate - retention).strftime("%Y%m%d")

    result = ec2.describe_images(Filters=[{
            'Name': 'name',
            'Values': [
                '*' + backupid +'*',
            ]
        },
    ],)

    print json.dumps(result)

    for image in result["Images"]:
        imagename = image["Name"]
        imageid = image["ImageId"]
        creationdate = imagename[-8:]
        print "creationdate: " + str(creationdate)
        print "datetodelete: " + str(datetodelete)
        if int(creationdate) <= int(datetodelete):
            imagestodelete.append(imageid)
            for blockdevice in image["BlockDeviceMappings"]:
                if blockdevice["Ebs"]:
                    snapshot = blockdevice["Ebs"]["SnapshotId"]
                    snapshotstodelete.append(snapshot)

    print "imagestodelete: " + json.dumps(imagestodelete)
    print "snapshotstodelete: " + json.dumps(snapshotstodelete)

    for image in imagestodelete:
        result = ec2.deregister_image(ImageId=image, DryRun=False)
    for snapshot in snapshotstodelete:
        result = ec2.delete_snapshot(SnapshotId=snapshot, DryRun=False)

getInventory()
createBackup()
removeOld()
