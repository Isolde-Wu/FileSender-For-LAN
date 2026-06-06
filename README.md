# FileSender For LAN

**A file transfer script suitable for a local area network, with mutual discovery functionality.**
###### Developed by Isolde
---

### How To Install ? 
You can Clone this project
#### For Linux and MacOS
```
git clone github.com/Isolde-Wu/FileSender-For-LAN
```
#### For Powershell on Windows Platform
```
$client = New-Object System.Net.WebClient
$client.DownloadFile('https://github.com/Isolde-Wu/FileSender-For-LAN/archive/refs/heads/main.zip', <the path you want to save to!!!> )
```
If you are using Windows *PowerShell* , please don't forget to change **<The path you want to save to!!!>**
  
  
### How To Run ?
Before starting, you need to make sure that you have a usable Python interpreter **(3.1 or newer)** installed on your computer (**Internet Connection Required**) . 
You can install it from these ways:
#### For Powershell on Windows Platform
```
wget -O <Path you want to download the installer to> https://www.python.org/ftp/python/3.11.0/python-3.11.0.exe ; cmd /c <Path you want to download the installer to> /quiet TargetDir=<Path you want to install to> InstallAllUsers=1 PrependPath=1 Include_test=0
```
Do not forget to change <**path you want to download the installer to**> and <**path you want to install to**>
#### For Debian or Ubuntu
```
sudo apt-get update
sudo apt-get install python3
```
#### For CentOS or RHCL
```
sudo yum update
sudo yum install python3
```
You can specify the version number, for example:```sudo apt-get install python3.8```
This method will automatically handle dependencies and is more suitable for server use.

