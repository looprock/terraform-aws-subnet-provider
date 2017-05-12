# terraform-aws-subnet-provider
Use as an external data source to find unused subnets

# How

aws-subnet-provider.py polls AWS for a cidr (usually your VPS cidr) and all it's subnets then translates them into a list of IPs to compare against. It then tries to determine the next available subnet of size 'prefix' (default: /26) and validates again the used IP list, and provides you with the next available range matching your criteria. It maintains a per-run cache file to make sure it doesn't re-assign the same range when calculating multiple subnets.

# example terraform implementation

```
data "external" "priv_subnets" {
  program = ["${path.module}/aws-cidr-cli.py"]
  query = {
    label = "us-east-2a-private,us-east-2b-private,us-east-2c-private"
    vpc = "${var.vpc_cidr}"
  }
}
# the default is a /26, we'll give the public subnets less IPs
data "external" "pub_subnets" {
  program = ["${path.module}/aws-cidr-cli.py"]
  query = {
    label = "us-east-2a-public,us-east-2b-public,us-east-2c-public"
    vpc = "${var.vpc_cidr}"
    prefix = "27"
  }
}

# create private subnet
resource "aws_subnet" "us-east-2a-private" {
   vpc_id = "${lookup(var.vpcids, var.region)}"
   availability_zone = "us-east-2a"
   cidr_block = "${data.external.priv_subnets.result.us-east-2a-private}"
   tags {
      Name = "${var.nametag}-us-east-2a-private"
      KubernetesCluster = "${var.nametag}"
      "kubernetes.io/role/internal-elb" = "true"
   }
}

resource "aws_subnet" "us-east-2a-public" {
   vpc_id = "${lookup(var.vpcids, var.region)}"
   availability_zone = "us-east-2a"
   map_public_ip_on_launch = true
   cidr_block = "${data.external.pub_subnets.result.us-east-2a-public}"
   tags {
      Name = "${var.nametag}-us-east-2a-public"
      KubernetesCluster = "${var.nametag}"
      "kubernetes.io/role/elb" = "true"
   }
}
```
