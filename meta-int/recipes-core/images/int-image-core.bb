require int-image-minimal.bb
SUMMARY = "INT console core with owner enrollment and default firewall"
IMAGE_INSTALL:append = " int-firstboot nftables kernel-module-nft-ct kernel-module-nf-conntrack"
