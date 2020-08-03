# SDS011
Python Interface with Nova Fitness SDS011 sensor, running multiple sensors at once. Built from the datasheet

## Set up
- SDS011 (or SDS018) connected with TTL UART adapter (5V)

## How to use the script

1. You connect all the SDS011 sensors to USB hub (via UART adapter), then you can run all of them at once:
```
  usbs = get_usb()
  processs = list()
  for port in usbs:
      p = SDS011(port=port, push_mqtt=False, interval=10)
      processs.append(p)

  while True:
      for p in processs:
          try:
              p.run_passive()
              # p.set_active()
              # p.run_query()
          except Exception as e:
              print(f'Error: {p.name} with {e}')
              continue
```
- by default, the data is saved to CSV file in each folder named after **month and year**
```
p = SDS011(port=port, save_data=False, interval=10)
```


## Datasheet
- Datasheet SDS011 [online](https://www-sd-nf.oss-cn-beijing.aliyuncs.com/%E5%AE%98%E7%BD%91%E4%B8%8B%E8%BD%BD/SDS011%20laser%20PM2.5%20sensor%20specification-V1.4.pdf) or in datasheet folder
- Communication Protocol: check out datasheet folder
