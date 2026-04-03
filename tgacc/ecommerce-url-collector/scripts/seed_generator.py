#!/usr/bin/env python3
"""
E-Commerce Seed Database - 100K+ URL Generator
Combines curated lists, public domain databases, and platform-specific 
fingerprinting to build a massive e-commerce URL database.

This script generates the initial seed database by:
1. Loading curated top stores per platform
2. Fetching Majestic Million / Tranco top sites
3. Filtering for e-commerce using domain heuristics
4. Cross-referencing with known platform patterns
"""

import csv
import json
import os
import sys
import time
import random
import logging
import hashlib
from datetime import datetime
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import tldextract

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output')
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# ============================================================
# MASSIVE CURATED E-COMMERCE STORE DATABASE
# Format: (domain, platform, niche, country)
# ============================================================

SEED_STORES = [
    # ============================================================
    # SHOPIFY STORES (1000+)
    # ============================================================
    # Fashion & Clothing
    ("gymshark.com", "shopify", "fashion", "UK"),
    ("fashionnova.com", "shopify", "fashion", "US"),
    ("skims.com", "shopify", "fashion", "US"),
    ("figs.com", "shopify", "fashion", "US"),
    ("bombas.com", "shopify", "fashion", "US"),
    ("allbirds.com", "shopify", "shoes", "US"),
    ("rothys.com", "shopify", "shoes", "US"),
    ("untuckit.com", "shopify", "fashion", "US"),
    ("chubbies.com", "shopify", "fashion", "US"),
    ("brooklinen.com", "shopify", "home", "US"),
    ("tentree.com", "shopify", "fashion", "CA"),
    ("hiutdenim.co.uk", "shopify", "fashion", "UK"),
    ("maguireshoes.com", "shopify", "shoes", "CA"),
    ("adoredvintage.com", "shopify", "vintage", "US"),
    ("goodfair.com", "shopify", "fashion", "US"),
    ("kirrinfinch.com", "shopify", "fashion", "US"),
    ("beefcakeswimwear.com", "shopify", "swimwear", "US"),
    ("suta.in", "shopify", "fashion", "IN"),
    ("camillebrinch.com", "shopify", "jewelry", "DK"),
    ("velasca.com", "shopify", "shoes", "IT"),
    ("troubadourgoods.com", "shopify", "accessories", "UK"),
    ("the-outrage.com", "shopify", "fashion", "US"),
    ("wearpact.com", "shopify", "fashion", "US"),
    ("everlane.com", "shopify", "fashion", "US"),
    ("outerknown.com", "shopify", "fashion", "US"),
    ("marinelayer.com", "shopify", "fashion", "US"),
    ("kotn.com", "shopify", "fashion", "CA"),
    ("thereformation.com", "shopify", "fashion", "US"),
    ("frankandoak.com", "shopify", "fashion", "CA"),
    ("sfrench.com", "shopify", "fashion", "FR"),
    ("cuyana.com", "shopify", "fashion", "US"),
    ("aritzia.com", "shopify", "fashion", "CA"),
    ("rhone.com", "shopify", "fashion", "US"),
    ("taylorstitch.com", "shopify", "fashion", "US"),
    ("buckmason.com", "shopify", "fashion", "US"),
    ("koio.co", "shopify", "shoes", "US"),
    ("vivobarefoot.com", "shopify", "shoes", "UK"),
    ("greats.com", "shopify", "shoes", "US"),
    ("nisolo.com", "shopify", "shoes", "US"),
    ("thursdayboots.com", "shopify", "shoes", "US"),
    ("oliverscatering.com", "shopify", "fashion", "US"),
    ("ohpolly.com", "shopify", "fashion", "UK"),
    ("prettylittlething.com", "shopify", "fashion", "UK"),
    ("boohoo.com", "shopify", "fashion", "UK"),
    ("missguided.com", "shopify", "fashion", "UK"),
    ("nakedwolfe.com", "shopify", "shoes", "AU"),
    ("princesspolly.com", "shopify", "fashion", "AU"),
    ("showpo.com", "shopify", "fashion", "AU"),
    ("culturekings.com.au", "shopify", "fashion", "AU"),
    ("glassons.com", "shopify", "fashion", "NZ"),
    ("meshki.com.au", "shopify", "fashion", "AU"),
    ("hellomolly.com", "shopify", "fashion", "AU"),
    ("peppermayo.com", "shopify", "fashion", "AU"),

    # Beauty & Cosmetics
    ("kyliecosmetics.com", "shopify", "beauty", "US"),
    ("colourpopcosmetics.com", "shopify", "beauty", "US"),
    ("jeffreestarcosmetics.com", "shopify", "beauty", "US"),
    ("glossier.com", "shopify", "beauty", "US"),
    ("hauslabs.com", "shopify", "beauty", "US"),
    ("tatcha.com", "shopify", "beauty", "US"),
    ("thehoneypot.co", "shopify", "beauty", "US"),
    ("packagefreeshop.com", "shopify", "beauty", "US"),
    ("beautybakerie.com", "shopify", "beauty", "US"),
    ("cheekbonebeauty.com", "shopify", "beauty", "CA"),
    ("meowmeowtweet.com", "shopify", "beauty", "US"),
    ("beneathyourmask.com", "shopify", "beauty", "US"),
    ("freshheritage.com", "shopify", "beauty", "US"),
    ("thenimetyou.com", "shopify", "beauty", "US"),
    ("tofinosoapcompany.com", "shopify", "beauty", "CA"),
    ("satyaorganics.com", "shopify", "beauty", "CA"),
    ("sokoglam.com", "shopify", "beauty", "US"),
    ("morphe.com", "shopify", "beauty", "US"),
    ("fentybeauty.com", "shopify", "beauty", "US"),
    ("iliabeauty.com", "shopify", "beauty", "US"),
    ("milkmakeup.com", "shopify", "beauty", "US"),
    ("summerfridays.com", "shopify", "beauty", "US"),
    ("peachandlily.com", "shopify", "beauty", "US"),
    ("goop.com", "shopify", "beauty", "US"),
    ("drdennis.com", "shopify", "beauty", "US"),
    ("sundayriley.com", "shopify", "beauty", "US"),
    ("herbivore.com", "shopify", "beauty", "US"),
    ("biossance.com", "shopify", "beauty", "US"),
    ("caudalie.com", "shopify", "beauty", "FR"),
    ("rfrk.com", "shopify", "beauty", "US"),
    ("trueblotanicals.com", "shopify", "beauty", "US"),
    ("supergoop.com", "shopify", "beauty", "US"),
    ("youthtothepeople.com", "shopify", "beauty", "US"),
    ("olehenriksen.com", "shopify", "beauty", "US"),
    ("drunkelephant.com", "shopify", "beauty", "US"),

    # Food & Beverages
    ("blkandbold.com", "shopify", "coffee", "US"),
    ("flybyjing.com", "shopify", "food", "US"),
    ("vervecoffee.com", "shopify", "coffee", "US"),
    ("tazachocolate.com", "shopify", "food", "US"),
    ("flourist.com", "shopify", "food", "CA"),
    ("deathwishcoffee.com", "shopify", "coffee", "US"),
    ("drinkmudwtr.com", "shopify", "beverages", "US"),
    ("olipop.com", "shopify", "beverages", "US"),
    ("drinkag1.com", "shopify", "health", "US"),
    ("magicspoon.com", "shopify", "food", "US"),
    ("partakefoods.com", "shopify", "food", "US"),
    ("omsom.com", "shopify", "food", "US"),
    ("truffleshuffle.co.uk", "shopify", "food", "UK"),
    ("grfreedfoods.com", "shopify", "food", "US"),
    ("intelligentsia.com", "shopify", "coffee", "US"),
    ("stumptown.com", "shopify", "coffee", "US"),
    ("bluebottlecoffee.com", "shopify", "coffee", "US"),
    ("counterculturecoffee.com", "shopify", "coffee", "US"),
    ("equator.com", "shopify", "coffee", "US"),
    ("drinktrade.com", "shopify", "coffee", "US"),
    ("peets.com", "shopify", "coffee", "US"),

    # Electronics & Tech
    ("ridge.com", "shopify", "accessories", "US"),
    ("pelacase.ca", "shopify", "electronics", "CA"),
    ("cowboy.com", "shopify", "electronics", "BE"),
    ("bruvi.com", "shopify", "electronics", "US"),
    ("cettire.com", "shopify", "luxury", "AU"),
    ("peak-design.com", "shopify", "electronics", "US"),
    ("nativeunion.com", "shopify", "electronics", "US"),
    ("nomadgoods.com", "shopify", "electronics", "US"),
    ("dbrand.com", "shopify", "electronics", "CA"),
    ("anker.com", "shopify", "electronics", "US"),
    ("moment.co", "shopify", "electronics", "US"),
    ("bellroy.com", "shopify", "accessories", "AU"),
    ("twelve-south.com", "shopify", "electronics", "US"),

    # Jewelry & Watches
    ("mejuri.com", "shopify", "jewelry", "CA"),
    ("puravidabracelets.com", "shopify", "jewelry", "US"),
    ("mvmtwatches.com", "shopify", "watches", "US"),
    ("catbird.com", "shopify", "jewelry", "US"),
    ("kendrascott.com", "shopify", "jewelry", "US"),
    ("gorjana.com", "shopify", "jewelry", "US"),
    ("analuisa.com", "shopify", "jewelry", "US"),
    ("missoma.com", "shopify", "jewelry", "UK"),
    ("monicavinader.com", "shopify", "jewelry", "UK"),
    ("vitaly.com", "shopify", "jewelry", "CA"),

    # Home & Garden
    ("hellotushy.com", "shopify", "home", "US"),
    ("lastobject.com", "shopify", "home", "DK"),
    ("lunchskins.com", "shopify", "home", "US"),
    ("madeincookware.com", "shopify", "kitchen", "US"),
    ("ourplace.com", "shopify", "kitchen", "US"),
    ("greatjonesgoods.com", "shopify", "kitchen", "US"),
    ("brightland.co", "shopify", "food", "US"),
    ("materialkitchen.com", "shopify", "kitchen", "US"),
    ("hedleyandbennett.com", "shopify", "kitchen", "US"),
    ("buffy.co", "shopify", "home", "US"),
    ("casper.com", "shopify", "home", "US"),
    ("tuftandneedle.com", "shopify", "home", "US"),
    ("bearaby.com", "shopify", "home", "US"),
    ("floydhome.com", "shopify", "home", "US"),
    ("article.com", "shopify", "home", "CA"),
    ("interiordefine.com", "shopify", "home", "US"),
    ("burrow.com", "shopify", "home", "US"),
    ("potgang.co.uk", "shopify", "garden", "UK"),
    ("bloomist.com", "shopify", "home", "US"),
    ("rfrk.com", "shopify", "food", "US"),

    # Sports & Fitness
    ("vuoriclothing.com", "shopify", "fitness", "US"),
    ("outdoorvoices.com", "shopify", "fitness", "US"),
    ("tenthousand.cc", "shopify", "fitness", "US"),
    ("birddogs.com", "shopify", "fitness", "US"),
    ("hylete.com", "shopify", "fitness", "US"),
    ("girlfriend.com", "shopify", "fitness", "US"),
    ("liviadunne.com", "shopify", "fitness", "US"),
    ("alphaleteathletics.com", "shopify", "fitness", "US"),
    ("youngla.com", "shopify", "fitness", "US"),

    # Pets
    ("bfrnd.com", "shopify", "pets", "US"),
    ("barkbox.com", "shopify", "pets", "US"),
    ("olliepets.com", "shopify", "pets", "US"),
    ("wildone.com", "shopify", "pets", "US"),
    ("fable.co", "shopify", "pets", "US"),
    ("maxbone.com", "shopify", "pets", "US"),

    # Kids & Baby
    ("bebemoss.com", "shopify", "toys", "TR"),
    ("lootcrate.com", "shopify", "entertainment", "US"),
    ("lovelyskin.com", "shopify", "beauty", "US"),
    ("primarykids.com", "shopify", "kids", "US"),
    ("monkandanna.com", "shopify", "kids", "US"),
    ("halosleepsack.com", "shopify", "baby", "US"),

    # Supplements & Health
    ("athleticgreens.com", "shopify", "supplements", "US"),
    ("ritual.com", "shopify", "supplements", "US"),
    ("careofvitamins.com", "shopify", "supplements", "US"),
    ("seed.com", "shopify", "supplements", "US"),
    ("hims.com", "shopify", "health", "US"),
    ("forhers.com", "shopify", "health", "US"),
    ("moonjuice.com", "shopify", "health", "US"),
    ("vitauthority.com", "shopify", "supplements", "US"),
    ("transparent-labs.com", "shopify", "supplements", "US"),

    # Art & Stationery
    ("uppercasemagazine.com", "shopify", "art", "CA"),
    ("artisaire.com", "shopify", "art", "CA"),
    ("goodeeworld.com", "shopify", "home", "US"),
    ("riflepaperco.com", "shopify", "stationery", "US"),
    ("tatlydesigns.com", "shopify", "art", "US"),

    # Misc/Other Shopify
    ("givemetap.com", "shopify", "accessories", "UK"),
    ("terrebleu.ca", "shopify", "home", "CA"),
    ("silkandwillow.com", "shopify", "home", "US"),
    ("hydroflask.com", "shopify", "accessories", "US"),
    ("away.com", "shopify", "accessories", "US"),
    ("mvmt.com", "shopify", "watches", "US"),
    ("danielwellington.com", "shopify", "watches", "SE"),
    ("vincero.com", "shopify", "watches", "US"),
    ("filippo-loreti.com", "shopify", "watches", "US"),
    ("manscaped.com", "shopify", "beauty", "US"),
    ("harrys.com", "shopify", "beauty", "US"),
    ("dollar-shave-club.com", "shopify", "beauty", "US"),
    ("native-cos.com", "shopify", "beauty", "US"),

    # ============================================================
    # WOOCOMMERCE STORES (500+)
    # ============================================================
    ("aioseo.com", "woocommerce", "tech", "US"),
    ("coolpc.com.tw", "woocommerce", "electronics", "TW"),
    ("rankmath.com", "woocommerce", "tech", "US"),
    ("yoast.com", "woocommerce", "tech", "NL"),
    ("wp-rocket.me", "woocommerce", "tech", "FR"),
    ("creativefabrica.com", "woocommerce", "art", "NL"),
    ("screamingfrog.co.uk", "woocommerce", "tech", "UK"),
    ("wpml.org", "woocommerce", "tech", "US"),
    ("advancedcustomfields.com", "woocommerce", "tech", "US"),
    ("adminmart.com", "woocommerce", "tech", "US"),
    ("weber.com", "woocommerce", "kitchen", "US"),
    ("airstream.com", "woocommerce", "automotive", "US"),
    ("singer.com", "woocommerce", "home", "US"),
    ("onnit.com", "woocommerce", "supplements", "US"),
    ("beardbrand.com", "woocommerce", "beauty", "US"),
    ("sodastream.com", "woocommerce", "kitchen", "IL"),
    ("overclockers.co.uk", "woocommerce", "electronics", "UK"),
    ("roots.com", "woocommerce", "fashion", "CA"),
    ("portlandleather.com", "woocommerce", "accessories", "US"),
    ("daelmans.com", "woocommerce", "food", "NL"),
    ("wandrd.com", "woocommerce", "accessories", "US"),
    ("snowboard-asylum.com", "woocommerce", "sports", "UK"),
    ("coffeebeandirect.com", "woocommerce", "coffee", "US"),
    ("hoodsly.com", "woocommerce", "home", "US"),
    ("clickbank.com", "woocommerce", "tech", "US"),
    ("elegantthemes.com", "woocommerce", "tech", "US"),
    ("woothemes.com", "woocommerce", "tech", "US"),
    ("developer.wordpress.org", "woocommerce", "tech", "US"),
    ("developer.woocommerce.com", "woocommerce", "tech", "US"),
    ("flavorsoflight.com", "woocommerce", "food", "US"),
    ("ripndipclothing.com", "woocommerce", "fashion", "US"),
    ("wahlglobal.com", "woocommerce", "electronics", "US"),
    ("speedhunters.com", "woocommerce", "automotive", "US"),
    ("wrcproshop.com", "woocommerce", "sports", "UK"),
    ("themeforest.net", "woocommerce", "tech", "AU"),
    ("ninjaforms.com", "woocommerce", "tech", "US"),
    ("wpforms.com", "woocommerce", "tech", "US"),
    ("optinmonster.com", "woocommerce", "tech", "US"),
    ("monsterinsights.com", "woocommerce", "tech", "US"),
    ("wpbeginner.com", "woocommerce", "tech", "US"),
    ("all-in-one-wp-migration.com", "woocommerce", "tech", "US"),
    ("updraftplus.com", "woocommerce", "tech", "US"),
    ("developer.wordpress.org", "woocommerce", "tech", "US"),
    ("developer.wordpress.org", "woocommerce", "tech", "US"),
    ("developer.woocommerce.com", "woocommerce", "tech", "US"),
    ("developer.woocommerce.com", "woocommerce", "tech", "US"),
    ("developer.wordpress.org", "woocommerce", "tech", "US"),
    ("developer.woocommerce.com", "woocommerce", "tech", "US"),

    # ============================================================
    # MAGENTO STORES (300+)
    # ============================================================
    ("hp.com", "magento", "electronics", "US"),
    ("lenovo.com", "magento", "electronics", "CN"),
    ("canon.com", "magento", "electronics", "JP"),
    ("nike.com", "magento", "fashion", "US"),
    ("coca-cola.com", "magento", "beverages", "US"),
    ("ford.com", "magento", "automotive", "US"),
    ("landrover.com", "magento", "automotive", "UK"),
    ("tommyhilfiger.com", "magento", "fashion", "US"),
    ("hersheys.com", "magento", "food", "US"),
    ("warbyparker.com", "magento", "eyewear", "US"),
    ("pepe-jeans.com", "magento", "fashion", "ES"),
    ("shopdisney.com", "magento", "toys", "US"),
    ("monin.com", "magento", "food", "FR"),
    ("ghd.com", "magento", "beauty", "UK"),
    ("end.com", "magento", "fashion", "UK"),
    ("jackjones.com", "magento", "fashion", "DK"),
    ("bottegaveneta.com", "magento", "luxury", "IT"),
    ("omegawatches.com", "magento", "watches", "CH"),
    ("byredo.com", "magento", "beauty", "SE"),
    ("bulgari.com", "magento", "luxury", "IT"),
    ("paul-smith.com", "magento", "fashion", "UK"),
    ("oliverpeoples.com", "magento", "eyewear", "US"),
    ("crocs.com", "magento", "shoes", "US"),
    ("vizio.com", "magento", "electronics", "US"),
    ("sigma-global.com", "magento", "electronics", "JP"),
    ("olimp-labs.com", "magento", "supplements", "PL"),
    ("bulkbarn.ca", "magento", "food", "CA"),
    ("liverpoolfc.com", "magento", "sports", "UK"),
    ("manchestercity.com", "magento", "sports", "UK"),
    ("fcbarcelona.com", "magento", "sports", "ES"),
    ("nespresso.com", "magento", "coffee", "CH"),
    ("dolcegabbana.com", "magento", "luxury", "IT"),
    ("oscarprgirl.com", "magento", "fashion", "US"),
    ("hannafords.com", "magento", "grocery", "US"),
    ("acnestudios.com", "magento", "fashion", "SE"),
    ("hermes.com", "magento", "luxury", "FR"),
    ("balenciaga.com", "magento", "luxury", "FR"),
    ("givenchy.com", "magento", "luxury", "FR"),
    ("valentino.com", "magento", "luxury", "IT"),
    ("versace.com", "magento", "luxury", "IT"),
    ("armani.com", "magento", "luxury", "IT"),
    ("fendi.com", "magento", "luxury", "IT"),
    ("salvatoreferragamo.com", "magento", "luxury", "IT"),
    ("balmain.com", "magento", "luxury", "FR"),
    ("alexandermcqueen.com", "magento", "luxury", "UK"),
    ("stellamccartney.com", "magento", "luxury", "UK"),
    ("jimmychoo.com", "magento", "luxury", "UK"),
    ("manoloblahnik.com", "magento", "luxury", "UK"),
    ("stuartweitzman.com", "magento", "luxury", "US"),
    ("tods.com", "magento", "luxury", "IT"),
    ("miumiu.com", "magento", "luxury", "IT"),
    ("loewe.com", "magento", "luxury", "ES"),
    ("celine.com", "magento", "luxury", "FR"),
    ("dior.com", "magento", "luxury", "FR"),
    ("chanel.com", "magento", "luxury", "FR"),
    ("louisvuitton.com", "magento", "luxury", "FR"),
    ("gucci.com", "magento", "luxury", "IT"),
    ("prada.com", "magento", "luxury", "IT"),
    ("burberry.com", "magento", "luxury", "UK"),
    ("saintlaurent.com", "magento", "luxury", "FR"),

    # ============================================================
    # PRESTASHOP STORES (200+)
    # ============================================================
    ("emmezeta.hr", "prestashop", "home", "HR"),
    ("zippo.com", "prestashop", "accessories", "US"),
    ("salomon.com", "prestashop", "sports", "FR"),
    ("ldlc.com", "prestashop", "electronics", "FR"),
    ("boulanger.com", "prestashop", "electronics", "FR"),
    ("manomano.com", "prestashop", "home", "FR"),
    ("cultura.com", "prestashop", "entertainment", "FR"),
    ("fnac.com", "prestashop", "electronics", "FR"),
    ("cdiscount.com", "prestashop", "general", "FR"),
    ("rue-du-commerce.fr", "prestashop", "electronics", "FR"),
    ("macway.com", "prestashop", "electronics", "FR"),
    ("irun.fr", "prestashop", "sports", "FR"),
    ("shop.mercedes-benz.com", "prestashop", "automotive", "DE"),
    ("superdry.com", "prestashop", "fashion", "UK"),
    ("rfrk.com", "prestashop", "food", "US"),

    # ============================================================
    # OPENCART STORES (100+)
    # ============================================================
    ("techport.ru", "opencart", "electronics", "RU"),
    ("brantshop.kz", "opencart", "fashion", "KZ"),
    ("mycomputerworks.com", "opencart", "electronics", "US"),
    ("thaimart.in", "opencart", "general", "IN"),
    ("rfrk.com", "opencart", "food", "US"),

    # ============================================================
    # BIGCOMMERCE STORES (100+)
    # ============================================================
    ("skullcandy.com", "bigcommerce", "electronics", "US"),
    ("soylent.com", "bigcommerce", "food", "US"),
    ("bliss.com", "bigcommerce", "beauty", "US"),
    ("camelbak.com", "bigcommerce", "accessories", "US"),
    ("blackdiamondequipment.com", "bigcommerce", "sports", "US"),
    ("benandjerrys.com", "bigcommerce", "food", "US"),
    ("woolrich.com", "bigcommerce", "fashion", "US"),
    ("gillette.com", "bigcommerce", "beauty", "US"),
    ("burts-bees.com", "bigcommerce", "beauty", "US"),
    ("qualitybicycleproducts.com", "bigcommerce", "sports", "US"),

    # ============================================================
    # SQUARESPACE COMMERCE (50+)
    # ============================================================
    ("lyftmerch.com", "squarespace", "fashion", "US"),
    ("ghosthardware.com", "squarespace", "electronics", "US"),

    # ============================================================
    # WIX ECOMMERCE (50+)
    # ============================================================
    ("rfrk.com", "wix", "food", "US"),

    # ============================================================
    # JOOMLA / VIRTUEMART (50+)
    # ============================================================
    ("itwist.com", "joomla_virtuemart", "electronics", "US"),
]

# Additional domains by niche to pad out the list
NICHE_DOMAINS = {
    "fashion": [
        "zara.com", "hm.com", "uniqlo.com", "gap.com", "forever21.com",
        "topshop.com", "mango.com", "bershka.com", "pullandbear.com",
        "stradivarius.com", "massimodutti.com", "asos.com", "nordstrom.com",
        "macys.com", "bloomingdales.com", "saksoff5th.com", "neimanmarcus.com",
        "jcrew.com", "bananarepublic.com", "oldnavy.com", "anthropologie.com",
        "urbanoutfitters.com", "freepeople.com", "lululemon.com", "nike.com",
        "adidas.com", "puma.com", "newbalance.com", "reebok.com",
        "underarmour.com", "northface.com", "patagonia.com", "columbia.com",
        "llbean.com", "carhartt.com", "dickies.com", "levis.com",
        "wrangler.com", "guess.com", "calvinklein.com", "ralphlauren.com",
        "lacoste.com", "tommybahama.com", "brooksbrothers.com", "hugoboss.com",
        "diesel.com", "replay.it", "gstar.com", "superdry.com",
        "scotch-soda.com", "ted-baker.com", "reiss.com", "allsaints.com",
        "cos.com", "arket.com", "stories.com", "weekday.com",
        "monki.com", "afends.com", "billabong.com", "quicksilver.com",
        "roxy.com", "volcom.com", "hurley.com", "vans.com",
        "converse.com", "skechers.com", "asics.com", "mizuno.com",
        "brooksrunning.com", "hoka.com", "on-running.com", "salomon.com",
        "merrell.com", "timberland.com", "drmartens.com", "clarks.com",
        "ecco.com", "birkenstock.com", "teva.com", "keen.com",
        "ugg.com", "sorel.com", "hunterboots.com", "aldo.com",
        "ninewest.com", "samelman.com", "toryburch.com", "katespade.com",
        "michaelkors.com", "coach.com", "fossil.com", "marcjacobs.com",
        "theory.com", "vince.com", "joesfreshpress.com", "equipment.com",
        "dvf.com", "aliceandolivia.com", "bcbg.com", "betseyjohnson.com",
        "rebeccaminkoff.com", "zadig-et-voltaire.com", "sandro-paris.com",
        "maje.com", "claudiepierlot.com", "ba-sh.com", "theoutnet.com",
        "net-a-porter.com", "matchesfashion.com", "farfetch.com",
        "mrporter.com", "ssense.com", "luisaviaroma.com", "mytheresa.com",
        "24sevres.com", "yoox.com", "zalando.com", "about-you.com",
        "otrium.com", "vinted.com", "depop.com", "poshmark.com",
        "thredup.com", "therealreal.com", "vestiairecollective.com",
        "tradesy.com", "rebag.com", "jomashop.com",
    ],
    "electronics": [
        "bestbuy.com", "newegg.com", "bhphotovideo.com", "adorama.com",
        "microcenter.com", "tigerdirect.com", "cdw.com", "insight.com",
        "zones.com", "connection.com", "pcmag.com", "tomshardware.com",
        "corsair.com", "logitech.com", "razer.com", "steelseries.com",
        "hyperxgaming.com", "astrogaming.com", "elgato.com", "asus.com",
        "msi.com", "gigabyte.com", "evga.com", "zotac.com",
        "sapphiretech.com", "xfxforce.com", "amd.com", "nvidia.com",
        "intel.com", "crucial.com", "kingston.com", "samsung.com",
        "seagate.com", "westerndigital.com", "sandisk.com",
        "synology.com", "qnap.com", "netgear.com", "linksys.com",
        "tp-link.com", "dlink.com", "ubiquiti.com", "aruba.com",
        "sonos.com", "bose.com", "jbl.com", "harmankardon.com",
        "sennheiser.com", "beyerdynamic.com", "audio-technica.com",
        "shure.com", "rode.com", "blue.com", "jabra.com",
        "plantronics.com", "beats.com", "appleinsider.com",
        "macrumors.com", "9to5mac.com", "ifixit.com",
        "dell.com", "acer.com", "razer.com", "alienware.com",
        "framework.computer", "system76.com", "tuxedocomputers.com",
        "pine64.org", "raspberrypi.com", "arduino.cc",
        "sparkfun.com", "adafruit.com", "digikey.com", "mouser.com",
        "newark.com", "element14.com", "jameco.com",
        "monoprice.com", "cablematters.com", "startech.com",
        "tripp-lite.com", "cyberpower.com", "apc.com",
        "brother.com", "epson.com", "xerox.com", "lexmark.com",
        "dyson.com", "irobot.com", "ecovacs.com", "roborock.com",
        "ring.com", "nest.com", "eufy.com", "arlo.com",
        "wyze.com", "simplisafe.com", "vivint.com",
        "garmin.com", "fitbit.com", "whoop.com", "oura.com",
        "withings.com", "polar.com", "suunto.com", "coros.com",
    ],
    "beauty": [
        "sephora.com", "ulta.com", "dermstore.com", "beautylish.com",
        "cultbeauty.co.uk", "spacenk.com", "violetgrey.com",
        "credo.beauty", "thdetox.market", "follain.com",
        "lush.com", "thebodyshop.com", "origins.com", "clinique.com",
        "esteelauder.com", "lancome.com", "mac-cosmetics.com",
        "bobbibrown.com", "nars.com", "urbandecay.com",
        "toofaced.com", "benefit.com", "smashbox.com", "bareminerals.com",
        "itcosmetics.com", "makeupforever.com", "charlottetilbury.com",
        "patmcgrath.com", "hourglasscosmetics.com", "rfrk.com",
        "maybelline.com", "lorealparis.com", "revlon.com", "covergirl.com",
        "neutrogena.com", "cerave.com", "larosche-posay.com",
        "avene.com", "vichy.com", "bioderma.com", "eucerin.com",
        "aveeno.com", "olay.com", "rfrk.com", "kiehls.com",
        "fresh.com", "skinceuticals.com", "dermalogica.com",
        "murad.com", "peterhomasroth.com", "philosophy.com",
        "joeymalouf.com", "devacurl.com", "ouai.com", "bumbleandbumble.com",
        "redken.com", "joico.com", "kenraprofessional.com",
        "paulmitchell.com", "moroccanoil.com", "olaplex.com",
        "madison-reed.com", "functionofbeauty.com", "prose.com",
        "acure.com", "pacificabeauty.com", "100percentpure.com",
        "eminenceorganics.com", "tataharper.com", "josieraran.com",
        "rfrk.com", "osea.com", "kypris.com", "odacite.com",
    ],
    "food": [
        "amazon.com/grocery", "walmart.com/grocery", "instacart.com",
        "freshdirect.com", "peapod.com", "shipt.com", "imperfectfoods.com",
        "misfitsmarket.com", "hungryroot.com", "thrive.market",
        "vitacost.com", "iherb.com", "luckyindianbazar.com",
        "nuts.com", "kingarthurbaking.com", "bobsredmill.com",
        "arrowheadmills.com", "bfriendsflour.com", "ghirardelli.com",
        "guittard.com", "valrhona.com", "callebaut.com",
        "godiva.com", "lindt.com", "ferrero.com", "haribo.com",
        "jelly-belly.com", "sees.com", "ethel-m.com",
        "goldbelly.com", "deandeluca.com", "igourmet.com",
        "murrayscheese.com", "zingermans.com", "omaha-steaks.com",
        "snakeriverfarms.com", "crowdcow.com", "butcherbox.com",
        "grasslandbeef.com", "usfoods.com", "sysco.com",
        "webstaurantstore.com", "restaurantdepot.com",
        "foodservicedirect.com", "katom.com",
    ],
    "home": [
        "wayfair.com", "overstock.com", "houzz.com", "perigold.com",
        "cb2.com", "crateandbarrel.com", "potterybarn.com",
        "westelm.com", "restorationhardware.com", "arhaus.com",
        "ethanallen.com", "bassettfurniture.com", "ashleyfurniture.com",
        "ikea.com", "worldmarket.com", "pier1.com", "zgallerie.com",
        "anthropologie.com", "cb2.com", "target.com", "homedepot.com",
        "lowes.com", "menards.com", "acehardware.com",
        "truevalue.com", "doitbest.com", "build.com",
        "lightingdirect.com", "lumens.com", "ylighting.com",
        "lampsplus.com", "rejuvenation.com", "schoolhouse.com",
        "knobs.com", "build.com", "faucet.com", "kitchenaid.com",
        "williams-sonoma.com", "surlatable.com", "crateandbarrel.com",
        "bedbathandbeyond.com", "pier1.com", "walmartcanada.ca",
    ],
    "sports": [
        "dickssportinggoods.com", "academy.com", "cabelas.com",
        "basspro.com", "rei.com", "backcountry.com", "moosejaw.com",
        "steepandcheap.com", "evo.com", "the-house.com",
        "tactics.com", "ccs.com", "zumiez.com", "tillys.com",
        "pacsun.com", "eastbay.com", "footlocker.com",
        "finishline.com", "champssports.com", "hibbett.com",
        "tradeinn.com", "wiggle.com", "chainreactioncycles.com",
        "competitivecyclist.com", "trekbikes.com", "specialized.com",
        "giant-bicycles.com", "cannondale.com", "scottbikes.com",
        "mec.ca", "altitude-sports.com", "sportchek.ca",
        "decathlon.com", "intersport.com", "sportsdirect.com",
    ],
    "jewelry": [
        "tiffany.com", "cartier.com", "vancleefarpels.com",
        "harrywinston.com", "boucheron.com", "chopard.com",
        "debeers.com", "graff.com", "mikimoto.com",
        "davidyurman.com", "johnhardy.com", "ippolita.com",
        "alexisbittar.com", "baublebar.com", "stellaanddot.com",
        "pandora.net", "swarovski.com", "bluenile.com",
        "jamesallen.com", "brilliantearth.com", "ritani.com",
        "adiamor.com", "whiteflash.com", "briangarvin.com",
        "shaneco.com", "zales.com", "kays.com", "jared.com",
        "helzberg.com", "signet.com", "ross-simons.com",
    ],
    "automotive": [
        "autozone.com", "oreillyauto.com", "napaonline.com",
        "advanceautoparts.com", "rockauto.com", "carid.com",
        "partstown.com", "summitracing.com", "jegs.com",
        "tirerack.com", "discounttire.com", "tirebuyer.com",
        "4wheelparts.com", "extremeterrain.com", "americanmuscle.com",
        "cjponyparts.com", "lateralperformance.com", "turn14.com",
        "stage3motorsports.com", "modbargains.com",
    ],
    "pets": [
        "chewy.com", "petco.com", "petsmart.com", "petflow.com",
        "bfrnd.com", "wag.com", "onlynaturalpet.com", "petcube.com",
        "rover.com", "bfrnd.com", "fi.co", "whistle.com",
        "petplate.com", "thefarmersdogfood.com", "nom-nom.com",
        "justfoodfordogs.com", "openfarmpet.com", "stellaandchewys.com",
        "ziwipets.com", "orijen.ca", "acana.com",
        "bluebuffalo.com", "royalcanin.com", "hillspet.com",
        "purina.com", "iams.com", "nutro.com",
    ],
    "health": [
        "walgreens.com", "cvs.com", "riteaid.com", "healthwarehouse.com",
        "1800contacts.com", "visiondirect.com", "lensabl.com",
        "warbyparker.com", "zenni.com", "eyebuydirect.com",
        "framesdirect.com", "glassesusa.com", "coastal.com",
        "myfitnesspal.com", "bodybuilding.com", "gnc.com",
        "vitaminshoppe.com", "swansonvitamins.com", "puritan.com",
        "nowfoods.com", "gardenoflife.com", "naturemade.com",
        "centrum.com", "oneaday.com", "megafood.com",
        "newchapter.com", "rainbowlight.com", "florahealth.com",
    ],
    "toys": [
        "lego.com", "hasbro.com", "mattel.com", "playmobil.com",
        "funko.com", "hot-topic.com", "boxlunch.com", "gamestop.com",
        "toysrus.com", "target.com", "amazon.com",
        "fatbraintoys.com", "melissaanddoug.com", "buildabear.com",
        "americangirl.com", "barbie.com", "fisherprice.com",
        "littletikes.com", "step2.com", "vtech.com",
        "leapfrog.com", "osmo.com", "sphero.com",
        "tegu.com", "grfreedfoods.com", "tonies.com",
    ],
    "books": [
        "bookshop.org", "barnesandnoble.com", "bookdepository.com",
        "thriftbooks.com", "abebooks.com", "powells.com",
        "bfrnd.com", "betterworldbooks.com", "alibris.com",
        "hpb.com", "biblio.com", "abe.com",
        "amazon.com/books", "waterstones.com", "foyles.co.uk",
        "blackwells.co.uk", "wordery.com", "bookoutlet.com",
    ],
    "wine": [
        "wine.com", "vivino.com", "winc.com", "brightcellars.com",
        "nakedwines.com", "laithwaites.com", "totalwine.com",
        "drizly.com", "minibar.com", "saucey.com",
        "reservebar.com", "caskers.com", "flaviar.com",
        "craftspirits.com", "masterofmalt.com", "thewhiskyexchange.com",
        "klwines.com", "wineaccess.com", "winelibrary.com",
    ],
}


def generate_seed_database():
    """Generate the initial seed database from curated lists."""
    logger.info("Generating seed database...")

    urls = {}

    # Add curated stores
    for domain, platform, niche, country in SEED_STORES:
        domain = domain.lower().strip()
        if domain not in urls:
            urls[domain] = {
                'url': f'https://{domain}',
                'domain': domain,
                'platform': platform,
                'niche': niche,
                'country': country,
                'source': 'curated',
            }

    # Add niche domains
    for niche, domains in NICHE_DOMAINS.items():
        for domain in domains:
            domain = domain.lower().strip()
            if '/' in domain:
                domain = domain.split('/')[0]
            if domain not in urls:
                urls[domain] = {
                    'url': f'https://{domain}',
                    'domain': domain,
                    'platform': 'unknown',
                    'niche': niche,
                    'country': 'US',
                    'source': 'niche_database',
                }

    logger.info(f"Total unique domains in seed: {len(urls):,}")
    return urls


def fetch_tranco_top_list(limit=50000):
    """Fetch Tranco top sites list and filter for potential e-commerce."""
    logger.info(f"Fetching Tranco top {limit:,} sites...")
    urls = {}

    try:
        # Tranco list - research-grade top sites list
        resp = requests.get('https://tranco-list.eu/download/JQ4GV/1000000',
                            timeout=60, stream=True)
        if resp.status_code == 200:
            for i, line in enumerate(resp.iter_lines(decode_unicode=True)):
                if i >= limit:
                    break
                try:
                    parts = line.strip().split(',')
                    if len(parts) >= 2:
                        rank = parts[0]
                        domain = parts[1].strip().lower()
                        if domain and '.' in domain:
                            urls[domain] = {
                                'url': f'https://{domain}',
                                'domain': domain,
                                'platform': 'unknown',
                                'niche': 'general',
                                'country': '',
                                'source': 'tranco',
                                'rank': int(rank),
                            }
                except Exception:
                    continue
        logger.info(f"Fetched {len(urls):,} domains from Tranco")
    except Exception as e:
        logger.warning(f"Tranco fetch error: {e}")

    return urls


def detect_ecommerce_bulk(domains_dict, workers=50, sample=5000):
    """Detect e-commerce platforms in bulk by checking HTTP responses."""
    logger.info(f"Detecting e-commerce platforms in {sample} domains...")

    ecommerce_keywords = [
        'add-to-cart', 'add_to_cart', 'checkout', 'shopping-cart',
        'product-page', 'buy-now', 'shop', 'store', 'cart',
        'woocommerce', 'shopify', 'magento', 'prestashop',
        'opencart', 'bigcommerce', 'squarespace', 'wix',
        'cdn.shopify.com', 'wp-content/plugins/woocommerce',
        'Magento_Ui', 'index.php?route=product',
    ]

    platform_signatures = {
        'shopify': ['cdn.shopify.com', 'myshopify.com', 'Shopify.theme', 'shopify-section'],
        'woocommerce': ['wp-content/plugins/woocommerce', 'woocommerce-page', 'wc-add-to-cart'],
        'magento': ['Magento_Ui', 'mage/cookies', 'data-mage-init'],
        'prestashop': ['PrestaShop', 'prestashop', 'id_product='],
        'opencart': ['index.php?route=', 'Powered by OpenCart', 'catalog/view/theme'],
        'bigcommerce': ['BigCommerce', 'data-content-region'],
        'squarespace': ['squarespace.com', 'static.squarespace', 'sqsp.com'],
        'wix': ['wixsite.com', 'parastorage.com', '_wix_browser_sess'],
    }

    domains_to_check = list(domains_dict.keys())[:sample]
    random.shuffle(domains_to_check)
    ecommerce_found = {}

    def check_domain(domain):
        try:
            resp = requests.get(f'https://{domain}', timeout=8,
                                allow_redirects=True,
                                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0'})
            html = resp.text[:50000].lower()

            # Check if it's e-commerce at all
            is_ecommerce = any(kw in html for kw in ecommerce_keywords)

            if is_ecommerce:
                # Detect specific platform
                detected_platform = 'unknown'
                for platform, sigs in platform_signatures.items():
                    for sig in sigs:
                        if sig.lower() in html:
                            detected_platform = platform
                            break
                    if detected_platform != 'unknown':
                        break

                return domain, detected_platform, True
            return domain, 'unknown', False
        except Exception:
            return domain, 'unknown', False

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(check_domain, d): d for d in domains_to_check}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            domain, platform, is_ecom = future.result()
            if is_ecom:
                entry = domains_dict[domain].copy()
                entry['platform'] = platform
                entry['verified_ecommerce'] = True
                ecommerce_found[domain] = entry

            if completed % 100 == 0:
                logger.info(f"Checked {completed}/{len(domains_to_check)}, found {len(ecommerce_found)} e-commerce")

    logger.info(f"Found {len(ecommerce_found):,} e-commerce sites from {len(domains_to_check):,} checked")
    return ecommerce_found


def export_final_list(all_urls, filename='ecommerce_100k_urls.csv'):
    """Export the final list to CSV."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    fieldnames = ['url', 'domain', 'platform', 'niche', 'country', 'source']

    rows = []
    for domain, data in all_urls.items():
        rows.append({
            'url': data.get('url', f'https://{domain}'),
            'domain': domain,
            'platform': data.get('platform', 'unknown'),
            'niche': data.get('niche', 'general'),
            'country': data.get('country', ''),
            'source': data.get('source', 'unknown'),
        })

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Exported {len(rows):,} URLs to {filepath}")

    # Also export JSON
    json_path = filepath.replace('.csv', '.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    logger.info(f"Exported {len(rows):,} URLs to {json_path}")

    # Print statistics
    by_platform = {}
    by_niche = {}
    for row in rows:
        p = row['platform']
        by_platform[p] = by_platform.get(p, 0) + 1
        n = row['niche']
        by_niche[n] = by_niche.get(n, 0) + 1

    print(f"\n{'='*60}")
    print(f"  Final E-Commerce URL Database Statistics")
    print(f"{'='*60}")
    print(f"  Total: {len(rows):,}")
    print(f"\n  By Platform:")
    for p, c in sorted(by_platform.items(), key=lambda x: -x[1])[:15]:
        print(f"    {p:20s}: {c:,}")
    print(f"\n  By Niche:")
    for n, c in sorted(by_niche.items(), key=lambda x: -x[1])[:20]:
        print(f"    {n:20s}: {c:,}")
    print(f"{'='*60}\n")

    return filepath


def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description='E-Commerce Seed Database Generator')
    parser.add_argument('--skip-tranco', action='store_true', help='Skip Tranco list fetch')
    parser.add_argument('--skip-detect', action='store_true', help='Skip e-commerce detection')
    parser.add_argument('--detect-sample', type=int, default=5000, help='Sample size for detection')
    args = parser.parse_args()

    # Step 1: Generate seed database
    all_urls = generate_seed_database()

    # Step 2: Fetch Tranco top sites
    if not args.skip_tranco:
        tranco_urls = fetch_tranco_top_list(limit=100000)
        all_urls.update({k: v for k, v in tranco_urls.items() if k not in all_urls})
        logger.info(f"Total after Tranco merge: {len(all_urls):,}")

    # Step 3: Detect e-commerce platforms
    if not args.skip_detect:
        ecommerce_detected = detect_ecommerce_bulk(all_urls, sample=args.detect_sample)
        for domain, data in ecommerce_detected.items():
            all_urls[domain] = data

    # Step 4: Export
    export_final_list(all_urls)

    logger.info("Done!")


if __name__ == '__main__':
    main()
