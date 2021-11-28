import boto3
import os
import time

# please enter your credentials to AWS
# you can find them in them in your IAM user
os.environ['AWS_ACCESS_KEY_ID'] = ''  # enter aws_access_key_id
os.environ['AWS_SECRET_ACCESS_KEY'] = ''  # enter aws_secret_access_key
os.environ['AWS_REGION'] = 'us-east-1'

client = boto3.client('ec2', region_name='us-east-1')  # creating the connection with aws
public_subnets_id = []
private_subnets_id = []
# all the different id`s in the one dict for the different functions to use
components_id = {'vpc_id': 0, 'igw_id': 0, 'subnet_id': 0, 'nat_id': 0, 'route_id': 0}


def create_vpc(name):
    """creating a vpc with a specific CiderBlock"""

    vpc = client.create_vpc(CidrBlock='10.0.0.0/16')
    time.sleep(5)
    vpc_id = vpc['Vpc']['VpcId']
    components_id['vpc_id'] = vpc_id  # inserting the id in the id dict
    client.create_tags(Resources=[vpc_id], Tags=[{'Key': 'Name', 'Value': name}])


def create_internet_gateway(name):
    """creating an internet gateway and attaching it to the vpc"""

    internet_gateway = client.create_internet_gateway()
    time.sleep(5)
    igw_id = internet_gateway['InternetGateway']['InternetGatewayId']
    components_id['igw_id'] = igw_id  # inserting the id in the id dict
    client.create_tags(Resources=[igw_id],  # naming the igw
                       Tags=[{'Key': 'Name', 'Value': name}])
    #  attaching the igw to the specific vpc we created
    client.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=components_id['vpc_id'])


def create_subnet(availability_zone, name, cider_block, is_public):
    """
    creating public or private subnet
    :param availability_zone: the availability_zone in which the subnet will be deployed
    :param name: name of the subnet (private or public)
    :param cider_block: the specific cider_block of the subnet
    :param is_public: is the subnet is public or privat
    """

    subnet = client.create_subnet(
        AvailabilityZone=availability_zone,
        CidrBlock=cider_block,
        VpcId=components_id['vpc_id'])
    time.sleep(5)
    subnet_id = subnet['Subnet']['SubnetId']
    components_id['subnet_id'] = subnet_id  # inserting the id to the id dict
    client.create_tags(Resources=[subnet_id], Tags=[{'Key': 'Name', 'Value': name}])

    # making the public subnets to Auto-assign public IPv4 address
    if is_public == 'yes':
        client.modify_subnet_attribute(MapPublicIpOnLaunch={'Value': True}, SubnetId=subnet_id)
        public_subnets_id.append(subnet_id)

    elif is_public == 'no':
        client.modify_subnet_attribute(MapPublicIpOnLaunch={'Value': False}, SubnetId=subnet_id)
        private_subnets_id.append(subnet_id)

    else:
        print('invalid choice of public of private subnet')


def create_NAT_gateway(subnet_id, name):
    """creating a NAT gateway with an elastic ip address"""

    nat = client.allocate_address(Domain='vpc')  # assigning an elastic id address to the NAT
    nat = client.create_nat_gateway(AllocationId=nat['AllocationId'], SubnetId=subnet_id)
    time.sleep(20)  # we need to wait for the NAT gateway to be created
    nat_id = nat['NatGateway']['NatGatewayId']
    components_id['nat_id'] = nat_id  # inserting the id to the id dict
    client.create_tags(Resources=[nat_id], Tags=[{'Key': 'Name', 'Value': name}])


def create_route_table(name):
    """creating a route table in the vpc"""

    route = client.create_route_table(VpcId=components_id['vpc_id'])
    time.sleep(5)
    route_id = route['RouteTable']['RouteTableId']
    components_id['route_id'] = route_id  # inserting the id to the id dict
    client.create_tags(Resources=[route_id], Tags=[{'Key': 'Name', 'Value': name}])


def create_route(Nat_or_igw, nat_id=0):
    """
    creating a route to the internet from NAT gateway or IGW
    :param Nat_or_igw: is the route going to be through NAT or internet gateway
    :param nat_id: the NAT id
    """
    if Nat_or_igw == 'igw':
        client.create_route(
            DestinationCidrBlock='0.0.0.0/0',
            GatewayId=components_id['igw_id'],
            RouteTableId=components_id['route_id'])
    elif Nat_or_igw == 'NAT':
        client.create_route(
            DestinationCidrBlock='0.0.0.0/0',
            NatGatewayId=nat_id,
            RouteTableId=components_id['route_id'])


def associate_route_table(subnet_id):
    """associating a subnet with a specific route table"""

    client.associate_route_table(
        RouteTableId=components_id['route_id'],
        SubnetId=subnet_id)


def main():
    """
    This is where the magic happens, the things that will be created are:
    1 main vpc, 4 subnets(2 public and 2 private), 3 route tables(1 public through igw
    and 2 private through NAT gateway), 1 internet gateway and 2 NAT gateways.
    the public subnet will be connected to the internet through igw and the private through NAT gateway.
    this main function is written to create this specific infrastructure but you can use the functions above
    and create whatever infrastructure you desire, have fun!
    """

    create_vpc('main_vpc')
    create_internet_gateway('main_igw')
    # create 4 subnets in 2 different AZ for high availability
    # type 'yes' in the last argument if the subnet is public and 'no' if its private
    create_subnet('us-east-1a', 'public_sub1', '10.0.1.0/24', 'yes')
    create_subnet('us-east-1b', 'public_sub2', '10.0.2.0/24', 'yes')
    create_subnet('us-east-1a', 'private_sub1', '10.0.3.0/24', 'no')
    create_subnet('us-east-1b', 'private_sub2', '10.0.4.0/24', 'no')

    #  if the route table is going to be connected to igw insert in the create route func 'igw'
    #  if the route table is going to be connected to NAT gateway insert in the create route func 'NAT'
    create_route_table('public_route_table')
    create_route('igw')
    associate_route_table(public_subnets_id[0])
    associate_route_table(public_subnets_id[1])

    # create 2 NAT gateways in 2 different AZ for high availability
    create_NAT_gateway(public_subnets_id[0], 'NAT1test')  # first NAT gateway

    create_route_table('private_route_table 1test')
    create_route('NAT', components_id['nat_id'])  # second argument is the NAT id that just have been created
    associate_route_table(private_subnets_id[0])

    create_NAT_gateway(public_subnets_id[1], 'NAT2test')  # second NAT gateway

    create_route_table('private_route_table 2test')
    create_route('NAT', components_id['nat_id'])  # second argument is the NAT id that just have been created
    associate_route_table(private_subnets_id[1])


if __name__ == '__main__':
    main()


