# MediaInfo/Release/BuildRelease.sh
# Build a release of MediaInfo

# Copyright (c) MediaArea.net SARL. All Rights Reserved.
# Use of this source code is governed by a BSD-style license that
# can be found in the License.html file in the root of the source
# tree.

function _mac_cli () {

    local sp RWDir

    # SSH prefix
    sp="ssh -x -p $MacSSHPort $MacSSHUser@$MacIP"
    RWDir="/Users/mymac/Documents/almin"

    cd "$MI_tmp"

    # Clean up
    $sp "cd $RWDir ;
            test -d build || mkdir build ;
            rm -fr build/MediaInfo_CLI*"

    echo
    echo "Compile MI CLI for mac..."
    echo

    scp -P $MacSSHPort prepare_source/archives/MediaInfo_CLI_${Version_new}_GNU_FromSource.tar.xz $MacSSHUser@$MacIP:$RWDir/build/MediaInfo_CLI_${Version_new}_GNU_FromSource.tar.xz
            #cd MediaInfo_CLI_${Version_new}_GNU_FromSource ;
    $sp "cd $RWDir/build ;
            tar xf MediaInfo_CLI_${Version_new}_GNU_FromSource.tar.xz ;
            cd MediaInfo_CLI_GNU_FromSource ;
            ./CLI_Compile.sh --enable-arch-x86_64 --enable-arch-i386"

    echo
    echo
    echo "DMG stage..."

            #cd MediaInfo_CLI_${Version_new}_GNU_FromSource ;
    $sp "cd $RWDir/build ;
            $KeyChain ;
            cd MediaInfo_CLI_GNU_FromSource/MediaInfo/Project/Mac ;
            ./mkdmg.sh mi cli $Version_new"

    scp -P $MacSSHPort "$MacSSHUser@$MacIP:$RWDir/build/MediaInfo_CLI_GNU_FromSource/MediaInfo/Project/Mac/MediaInfo_CLI_${Version_new}_Mac.dmg" "$MIC_dir"

}

function _mac_gui () {

    local sp RWDir

    # SSH prefix
    sp="ssh -x -p $MacSSHPort $MacSSHUser@$MacIP"
    RWDir="/Users/mymac/Documents/almin"

    cd "$MI_tmp"

    # Clean up
    $sp "cd $RWDir ;
            test -d build || mkdir build ;
            rm -fr build/MediaInfo_GUI*"

    echo
    echo "Compile MI GUI for mac..."
    echo

    scp -P $MacSSHPort prepare_source/archives/MediaInfo_GUI_${Version_new}_GNU_FromSource.tar.xz $MacSSHUser@$MacIP:$RWDir/build/MediaInfo_GUI_${Version_new}_GNU_FromSource.tar.xz
            #cd MediaInfo_GUI_${Version_new}_GNU_FromSource ;
    $sp "cd $RWDir/build ;
            tar xf MediaInfo_GUI_${Version_new}_GNU_FromSource.tar.xz ;
            cd MediaInfo_GUI_GNU_FromSource ;
            mkdir -p Shared/Source
            cp -r ../../WxWidgets Shared/Source ;
            ./GUI_Compile.sh --with-wx-static --enable-arch-x86_64"
            # Because wx doesn't compile in 32 bits
            #./GUI_Compile.sh --with-wx-static --enable-arch-x86_64 --enable-arch-i386"

    echo
    echo
    echo "DMG stage..."

            #cd MediaInfo_GUI_${Version_new}_GNU_FromSource ;
    $sp "cd $RWDir/build ;
            $KeyChain ;
            cd MediaInfo_GUI_GNU_FromSource/MediaInfo/Project/Mac ;
            ./mkdmg.sh mi gui $Version_new"

    if ! b.opt.has_flag? --snapshot; then

        echo
        echo
        echo "Preparing for the appstore..."
    
        rm -fr "$MI_tmp"/dylib
        mkdir "$MI_tmp"/dylib
        cd $(b.get bang.working_dir)
        $(b.get bang.src_path)/bang run BuildRelease.sh -wp "$MI_tmp"/dylib -p mil -s -o tmp -bm
        scp -P $MacSSHPort "$MI_tmp"/dylib/snapshots/binary/libmediainfo0/$Date/MediaInfo_DLL_tmp.${Date}_Mac_i386+x86_64.tar.xz $MacSSHUser@$MacIP:$RWDir/build/MediaInfo_GUI_GNU_FromSource/

                #cd MediaInfo_GUI_${Version_new}_GNU_FromSource ;
        $sp "cd $RWDir/build ;
                cd MediaInfo_GUI_GNU_FromSource ;
                mkdir dylib_for_xcode ;
                mv MediaInfo_DLL_tmp.${Date}_Mac_i386+x86_64.tar.xz dylib_for_xcode ;
                cd dylib_for_xcode ;
                tar xf MediaInfo_DLL_tmp.${Date}_Mac_i386+x86_64.tar.xz ;
                cp MediaInfoLib/libmediainfo.dylib ../MediaInfo/Source/GUI/Cocoa ;
                cd ../MediaInfo/Source/GUI/Cocoa ;
                install_name_tool -id @executable_path/../Resources/libmediainfo.dylib libmediainfo.dylib ;
                rm -fr *lproj ;
                cp -r ~/Documents/almin/xibs/* ."

    fi

    scp -P $MacSSHPort "$MacSSHUser@$MacIP:$RWDir/build/MediaInfo_GUI_GNU_FromSource/MediaInfo/Project/Mac/MediaInfo_GUI_${Version_new}_Mac.dmg" "$MIG_dir"

}

function _mac () {

    # TODO:
    # This function compile MIL, lauch the CLI and GUI compilation
    # with the compiled MIL folder, and mail in case of errors.

    local MultiArch Try

    cd "$MI_tmp"

    # Temporay fix for the autotools bug under mac. Check the size
    # to know if the compilation was successful. If not, retry to
    # compile up to 10 times.
    Try=0

    MultiArch=0
    touch "$MIC_dir"/MediaInfo_CLI_${Version_new}_Mac.dmg
    until [ `ls -l "$MIC_dir"/MediaInfo_CLI_${Version_new}_Mac.dmg |awk '{print $5}'` -gt 4000000 ] && [ $MultiArch -eq 1 ] || [ $Try -eq 10 ]; do
        if b.opt.has_flag? --log; then
            _mac_cli >> "$Log"/mac-cli.log 2>&1
        else
            _mac_cli
        fi
        # Return 1 if MI-cli is compiled for i386 and x86_64,
        # 0 otherwise
        #MultiArch=`ssh -x -p $MacSSHPort $MacSSHUser@$MacIP "file /Users/mymac/Documents/almin/build/MediaInfo_CLI_${Version_new}_GNU_FromSource/MediaInfo/Project/GNU/CLI/mediainfo" |grep "Mach-O universal binary with 2 architectures" |wc -l`
        MultiArch=`ssh -x -p $MacSSHPort $MacSSHUser@$MacIP "file /Users/mymac/Documents/almin/build/MediaInfo_CLI_GNU_FromSource/MediaInfo/Project/GNU/CLI/mediainfo" |grep "Mach-O universal binary with 2 architectures" |wc -l`
        Try=$(($Try + 1))
    done
    # TODO: send a mail if the build fail
    #if [ `ls -l "$MIC_dir"/MediaInfo_CLI_${Version_new}_Mac.dmg |awk '{print $5}'` -lt 4000000 ] || [ $MultiArch -eq 0 ]; then
    #    mail -s "Problem building MI-cli" someone@mediaarea.net < "The log is http://url/"$Log"/mac-cli.log"
    #fi

    Try=0
    touch "$MIG_dir"/MediaInfo_GUI_${Version_new}_Mac.dmg
    until [ `ls -l "$MIG_dir"/MediaInfo_GUI_${Version_new}_Mac.dmg |awk '{print $5}'` -gt 4000000 ] || [ $Try -eq 10 ]; do
        if b.opt.has_flag? --log; then
            _mac_gui >> "$Log"/mac-gui.log 2>&1
        else
            _mac_gui
        fi
        Try=$(($Try + 1))
    done

}

function _windows () {

    local sp RWDir

    # SSH prefix
    sp="ssh -x -p $WinSSHPort $WinSSHUser@$WinIP"
    RWDir="c:/Users/almin"

    cd "$MI_tmp"

    # Clean up
    $sp "c: & chdir $RWDir & rmdir /S /Q build"
    $sp "c: & chdir $RWDir & md build"

    echo
    echo "Compile MI CLI for windows..."
    echo

    scp -P $WinSSHPort prepare_source/archives/mediainfo_${Version_new}_AllInclusive.7z $WinSSHUser@$WinIP:$RWDir/build/mediainfo_${Version_new}_AllInclusive.7z
    $sp "c: & chdir $RWDir/build & \
            c:/\"Program Files\"/7-Zip/7z x mediainfo_${Version_new}_AllInclusive.7z & \

"
#            copy /Y ..\\MediaInfo.vcxproj mediainfo_AllInclusive\\MediaInfo\\Project\\MSVC2013\\CLI & \
#            copy /Y ..\\MediaInfoLib.vcxproj mediainfo_AllInclusive\\MediaInfoLib\\Project\\MSVC2013\\Library & \

#cd "C:\Program Files (x86)\Microsoft Visual Studio 12.0\VC\bin\amd64"
#%comspec% /k ""C:\Program Files (x86)\Microsoft Visual Studio 12.0\VC\vcvarsall.bat"" amd64
#cd C:\Users\almin\build\mediainfo_AllInclusive\MediaInfo\Project\MSVC2013\CLI
#msbuild MediaInfo.vcxproj


#    echo
#    echo "Compile MI CLI for mac..."
#    echo
#
#    scp -P $MacSSHPort prepare_source/archives/MediaInfo_CLI_${Version_new}_GNU_FromSource.tar.xz $MacSSHUser@$MacIP:$RWDir/build/MediaInfo_CLI_${Version_new}_GNU_FromSource.tar.xz
#            #cd MediaInfo_CLI_${Version_new}_GNU_FromSource ;
#    $sp "cd $RWDir/build ;
#            tar xf MediaInfo_CLI_${Version_new}_GNU_FromSource.tar.xz ;
#            cd MediaInfo_CLI_GNU_FromSource ;
#            ./CLI_Compile.sh --enable-arch-x86_64 --enable-arch-i386"
#
#    echo
#    echo "Compile MI GUI for mac..."
#    echo
#
#    scp -P $MacSSHPort prepare_source/archives/MediaInfo_GUI_${Version_new}_GNU_FromSource.tar.xz $MacSSHUser@$MacIP:$RWDir/build/MediaInfo_GUI_${Version_new}_GNU_FromSource.tar.xz
#            #cd MediaInfo_GUI_${Version_new}_GNU_FromSource ;
#    $sp "cd $RWDir/build ;
#            tar xf MediaInfo_GUI_${Version_new}_GNU_FromSource.tar.xz ;
#            cd MediaInfo_GUI_GNU_FromSource ;
#            mkdir -p Shared/Source
#            cp -r ../../WxWidgets Shared/Source ;
#            ./GUI_Compile.sh --with-wx-static --enable-arch-x86_64"
#            # Because wx doesn't compile in 32 bits
#            #./GUI_Compile.sh --with-wx-static --enable-arch-x86_64 --enable-arch-i386"
#
#    echo
#    echo "Making the dmg..."
#    echo
#
#            #cd MediaInfo_CLI_${Version_new}_GNU_FromSource ;
#            #cd MediaInfo_GUI_${Version_new}_GNU_FromSource ;
#    $sp "cd $RWDir/build ;
#            $KeyChain ;
#            cd MediaInfo_CLI_GNU_FromSource/MediaInfo/Project/Mac ;
#            ./mkdmg.sh mi cli $Version_new ;
#            cd - > /dev/null ;
#            cd MediaInfo_GUI_GNU_FromSource/MediaInfo/Project/Mac ;
#            ./mkdmg.sh mi gui $Version_new"
#
#    scp -P $MacSSHPort "$MacSSHUser@$MacIP:$RWDir/build/MediaInfo_CLI_GNU_FromSource/MediaInfo/Project/Mac/MediaInfo_CLI_${Version_new}_Mac.dmg" mac
#    scp -P $MacSSHPort "$MacSSHUser@$MacIP:$RWDir/build/MediaInfo_GUI_GNU_FromSource/MediaInfo/Project/Mac/MediaInfo_GUI_${Version_new}_Mac.dmg" mac

}

function _obs () {

    local OBS_Package="$OBS_Project/MediaInfo"

    cd "$MI_tmp"

    echo
    echo "Initialize OBS files..."
    echo

    osc checkout $OBS_Package

    # Clean up
    rm -f $OBS_Package/*

    cp prepare_source/archives/mediainfo_${Version_new}.tar.xz $OBS_Package
    cp prepare_source/archives/mediainfo_${Version_new}.tar.gz $OBS_Package

    #cp prepare_source/MI/MediaInfo_${Version_new}/Project/GNU/mediainfo.spec $OBS_Package
    #cp prepare_source/MI/MediaInfo_${Version_new}/Project/GNU/mediainfo.dsc $OBS_Package/mediainfo_${Version_new}.dsc
    cp prepare_source/MI/MediaInfo/Project/GNU/mediainfo.spec $OBS_Package
    cp prepare_source/MI/MediaInfo/Project/GNU/mediainfo.dsc $OBS_Package/mediainfo_${Version_new}.dsc

    update_DSC "$MI_tmp"/$OBS_Package mediainfo_${Version_new}.tar.xz mediainfo_${Version_new}.dsc

    cd $OBS_Package
    osc addremove *
    osc commit -n

}

function _obs_deb () {

    # This function build the source on OBS for a specific debian
    # version.

    local debVersion="$1" Comp="$2"
    local OBS_Package="$OBS_Project/MediaInfo_$debVersion"

    cd "$MI_tmp"

    echo
    echo "OBS for $OBS_Package, initialize files..."
    echo

    osc checkout $OBS_Package

    # Clean up
    rm -f $OBS_Package/*

    cp prepare_source/archives/mediainfo_${Version_new}.tar.$Comp $OBS_Package
    cd $OBS_Package
    tar xf mediainfo_${Version_new}.tar.$Comp
    rm -fr MediaInfo/debian
    mv MediaInfo/Project/OBS/${debVersion}.debian MediaInfo/debian
    if [ "$Comp" = "xz" ]; then
        (XZ_OPT=-9e tar -cJ --owner=root --group=root -f mediainfo_${Version_new}.tar.xz MediaInfo)
    elif [ "$Comp" = "gz" ]; then
        (GZIP=-9 tar -cz --owner=root --group=root -f mediainfo_${Version_new}.tar.gz MediaInfo)
    fi
    rm -fr MediaInfo
    cd ../..

    #cp prepare_source/MI/MediaInfo_${Version_new}/Project/OBS/${debVersion}.dsc $OBS_Package/mediainfo_${Version_new}.dsc
    cp prepare_source/MI/MediaInfo/Project/OBS/${debVersion}.dsc $OBS_Package/mediainfo_${Version_new}.dsc
    update_DSC "$MI_tmp"/$OBS_Package mediainfo_${Version_new}.tar.$Comp mediainfo_${Version_new}.dsc

    cd $OBS_Package
    osc addremove *
    osc commit -n

}

function _linux () {

    _obs
    _obs_deb deb7 xz
    _obs_deb deb6 gz

    # python script to update the DB, get the binaries and
    # generate the download webpage

}

function btask.BuildRelease.run () {

    # TODO: incremental snapshots if multiple execution in the
    # same day eg. AAAAMMJJ-X
    #if b.path.dir? $WDir/`date +%Y%m%d`; then
    #    mv $WDir/`date +%Y%m%d` $WDir/`date +%Y%m%d`-1
    #    WDir=$WDir/`date +%Y%m%d`-2
    #    mkdir -p $WDir
    # + handle a third run, etc
        
    local MIC_dir="$WDir"/binary/mediainfo/$Date
    local MIG_dir="$WDir"/binary/mediainfo-gui/$Date
    local MIS_dir="$WDir"/source/mediainfo/$Date
    local MI_tmp="$WDir"/tmp/mediainfo/$Date

    echo
    echo Clean up...
    echo

    rm -fr "$MIC_dir"
    rm -fr "$MIG_dir"
    rm -fr "$MIS_dir"
    rm -fr "$MI_tmp"

    mkdir -p "$MIC_dir"
    mkdir -p "$MIG_dir"
    mkdir -p "$MIS_dir"
    mkdir -p "$MI_tmp"

    cd "$MI_tmp"
    rm -fr upgrade_version
    rm -fr prepare_source
    mkdir upgrade_version
    mkdir prepare_source

    cd $(b.get bang.working_dir)/../upgrade_version
    if [ $(b.opt.get_opt --source-path) ]; then
        cp -r "$SDir" "$MI_tmp"/upgrade_version/MediaInfo
        $(b.get bang.src_path)/bang run UpgradeVersion.sh -p mi -o $Version_old -n $Version_new -sp "$MI_tmp"/upgrade_version/MediaInfo
    else
        $(b.get bang.src_path)/bang run UpgradeVersion.sh -p mi -o $Version_old -n $Version_new -wp "$MI_tmp"/upgrade_version
    fi

    cd $(b.get bang.working_dir)/../prepare_source
    # TODO: final version = remove -nc
    $(b.get bang.src_path)/bang run PrepareSource.sh -p mi -v $Version_new -wp "$MI_tmp"/prepare_source -sp "$MI_tmp"/upgrade_version/MediaInfo $PSTarget -nc

    if [ "$Target" = "mac" ]; then
        # The --log parameter is handled inside the _mac function
        _mac
        mv "$MI_tmp"/prepare_source/archives/MediaInfo_CLI_${Version_new}_GNU_FromSource.* "$MIC_dir"
        mv "$MI_tmp"/prepare_source/archives/MediaInfo_GUI_${Version_new}_GNU_FromSource.* "$MIG_dir"
    fi

    if [ "$Target" = "windows" ]; then
        if b.opt.has_flag? --log; then
            echo _windows > "$Log"/windows.log 2>&1
        else
            echo _windows
        fi
        mv "$MI_tmp"/prepare_source/archives/mediainfo_${Version_new}_AllInclusive.7z "$MIS_dir"
    fi
    
    if [ "$Target" = "linux" ]; then
        if b.opt.has_flag? --log; then
            _linux > "$Log"/linux.log 2>&1
        else
            _linux
        fi
        mv "$MI_tmp"/prepare_source/archives/mediainfo_${Version_new}.* "$MIS_dir"
    fi
    
    if [ "$Target" = "all" ]; then
        if b.opt.has_flag? --log; then
            _linux > "$Log"/linux.log 2>&1
            _mac
            echo _windows > "$Log"/windows.log 2>&1
        else
            _linux
            _mac
            echo _windows
        fi
        mv "$MI_tmp"/prepare_source/archives/MediaInfo_CLI_${Version_new}_GNU_FromSource.* "$MIC_dir"
        mv "$MI_tmp"/prepare_source/archives/MediaInfo_GUI_${Version_new}_GNU_FromSource.* "$MIG_dir"
        mv "$MI_tmp"/prepare_source/archives/mediainfo_${Version_new}_AllInclusive.7z "$MIS_dir"
        mv "$MI_tmp"/prepare_source/archives/mediainfo_${Version_new}.* "$MIS_dir"
    fi

    if $CleanUp; then
        # Can't rm $WDir/tmp/ or even $WDir/tmp/$Date, because
        # another instance of BS.sh can be running for another
        # project
        rm -fr "$MI_tmp"
    fi

}
