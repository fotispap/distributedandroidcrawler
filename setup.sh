rm -f apks/* 2>/dev/null
rm tempApks 2>/dev/null

printf "\n\nConnect a single device with all new versions of apps installed.\n"
read -n1 -r -p "Press space to continue..." key

for SERIAL in $(adb devices | tail -n +2 | cut -sf 1);
	do 
	  for INSTLIST in $(cat listapks);
		  do
		  	echo "----->Device $SERIAL; package name $INSTLIST<-----"
		  	adb -s $SERIAL shell "su -c 'ls data/app/$INSTLIST*' 2> /dev/null | tr -d '\r'" | head -n 1 >> tempApks;
		  done

	  for APK in $(cat tempApks)
	  	do
		    echo "-----> Retrieving $APK<------"
		    adb pull $APK apks/
		done
	done

echo "Apks that were retrieved:"
ls apks/
rm -f tempApks 2>/dev/null

printf "\n\nRetrieved apks present in listapks. Proceeding to static analysis.\n"
read -n1 -r -p "Press space to continue..." key

java -jar DroidBroker.jar -P

printf "\n\nPlease connect all devices (including previous one!). Proceeding to exporting results.\n"
read -n1 -r -p "Press space to continue..." key

./exportToDevices.sh

for SERIAL in $(adb devices | tail -n +2 | cut -sf 1);
	do 
		echo "$SERIAL has following apks installed : "

	  	for INSTLIST in $(cat listapks);
		  do
		  	echo "$(adb -s $SERIAL shell "su -c 'ls data/app/$INSTLIST*' 2> /dev/null | tr -d '\r'" | head -n 1)";
		  done

		echo "$SERIAL has following jsons placed : "
		echo "$(adb -s $SERIAL shell "su -c 'ls data/local/tmp/apkjsons/'")";

	done