# Dropit - Simple Cross-Platform File Sharing
![image](https://github.com/user-attachments/assets/0a711081-d9c2-4a95-9674-7239b76bcded)

![image](https://github.com/user-attachments/assets/a360f9b0-dac3-45dc-9678-0960a658588c)


## Introduction
Dropit simplifies the process of sharing files across multiple devices, including laptops and mobile phones, regardless of their operating system. Whether you're a developer working with multiple OS environments, or simply need to transfer files between devices, Dropit offers a straightforward solution.

## Key Features
- **Cross-Platform Compatibility**: Share files seamlessly between any devices on the same network.
- **Easy to Use**: Just a single command is needed to start sharing files.
- **Optional Password Protection**: Enhance security with an optional password.

## How to Use
To share files with Dropit, simply run the following command in your terminal:

```bash
dropit [--password <password>] [--geturl] [--getqr] [--maxsize <integer>]
```

*Options*
```
--password: <password>: Secures your file sharing session with basic authentication.
--geturl: Prints the URL to access Dropit from the other devices.
--getqr: Displays a QR code in the terminal, which can be scanned to connect to Dropit.
--maxsize <size_in_GB>: Sets a maximum file size for uploads (default is 2GB).
```
**NOTE**: The default username is `admin`

*Accessing Dropit:*

Open a web browser on any device connected to the same network and enter the URL displayed in the terminal. If a password is set, you will be prompted to enter it. 




### Additional Sections

#### Configuration Options
Detail other configuration settings if available, such as changing the default upload folder.


## Troubleshooting

- **Connection Issues**: Ensure all devices are on the same network. Check firewall settings if devices cannot connect to the server.
- **Performance Issues**: For large file transfers, ensure the server machine has sufficient resources. Consider increasing the system limits if uploads fail due to file size.
- **Mobile Device Compatibility**: Some mobile devices might experience difficulties accessing `http` URLs.



## Contributing

Contributions are welcome! If you have improvements or bug fixes, please open a pull request. For major changes, please open an issue first to discuss what you would like to change.
Please ensure to update tests as appropriate.


## Contributing

Contributions are welcome! If you have improvements or bug fixes, please open a pull request. For major changes, please open an issue first to discuss what you would like to change.
Please ensure to update tests as appropriate.
