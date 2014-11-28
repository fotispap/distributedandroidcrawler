#!/bin/bash

printf "\n\nExporting to devices! <------------------------------\n\n"

for SERIAL in $(adb devices | tail -n +2 | cut -sf 1);
do 

  echo "Uninstalling Apks!"

  for INSTLIST in $(cat listapks);
  do
    echo "----->Uninstalling $INSTLIST on $SERIAL<-----"
    adb -s $SERIAL shell pm uninstall $INSTLIST
  done

  echo "Installing Apks!"

  for APKLIST in apks/*.apk
  do
    echo "----->Exporting $APKLIST on $SERIAL<-----"
    adb -s $SERIAL install $APKLIST
  done

  echo "Removing json files from device!"
  adb -s $SERIAL shell "rm -f data/local/tmp/apkjsons/*" 2> /dev/null

  echo "Pushing new json files!"
  for JSONS in results/*.json
  do
    echo "----->Exporting $JSONS to $SERIAL<-----"
    adb -s $SERIAL push $JSONS data/local/tmp/apkjsons/
  done
done

echo "done! <----------------------------------------------"