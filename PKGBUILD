# Maintainer: Ybalrid <ybalrid@cecmu.org>
pkgname=numlockontty
pkgver=0.1
pkgrel=1
pkgdesc="Systemd service + script, automacily activate numpad on ttys"
arch=('any')
depends=(systemd, bash)
source=(http://datalove.cecmu.org/aur/$pkgname-$pkgver.tar.gz)
noextract=()
md5sums=() #generate with 'makepkg -g'


package() {
    chmod +x numlockOnTty
    cd "$srcdir/$pkgname-$pkgver"
    cp numlockOnTty /usr/bin/numlockOnTty
    cp numLockOnTty.service /etc/systemd/system/numLockOnTty.service
}
