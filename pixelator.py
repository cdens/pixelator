# pixelator.py
# Casey Densmore 01JAN2020
# 
# Generate a photomosaic given source image and photo library



#######################################################################################################################
#                                        IMPORT CALLS AND SUPPORT FUNCTIONS                                              #
#######################################################################################################################


# import calls
from cv2 import imread, resize, imwrite
import numpy as np
from os import listdir
import logging
import sys



# characterize image mean/standard deviations for RGB values
def getimgcolors(imgdata,classinterval,bounds,numclasses):
    meancolor = np.squeeze(resize(imgdata, (1,1)))
    stdev = getcolordifference(np.std(imgdata,axis=0),[0,0,0]) #standard deviation is magnitude of vector from 0,0,0
    return meancolor, stdev, classifycolorblock(meancolor,classinterval,bounds,numclasses)


#classifying color: each color is classified in one of 125 blocks given its color interval 
def classifycolorblock(color,classinterval,bounds,numclasses):    
    colorclasses = []
    
    for c in color:
        bottombound = -0.01 #negative number to ensure bottom bound includes 0
        for i,b in enumerate(bounds[1:]):
            if c > bottombound and c <= b:
                break
            else:
                bottombound = b
        colorclasses.append(i)
        
    colorblock = numclasses**2*colorclasses[0] + numclasses*colorclasses[1] + colorclasses[2]
    return colorblock
    
    
# characterize directory of images
def cacheimages(fullpath,pixwid,pixheight,classinterval,bounds,numclasses):
    
    allfiles = listdir(fullpath)
    allfiles.sort()
    allimages = {"data":[],"means":[],"stdevs":[],"block":[],"id":[],"ismatched":[]}
    
    imagedata = []
    imagemeans = []
    imagestdevs = []
    imageblocks = []
    imageids = []

    numfiles = len(allfiles)
    numonepct = np.round(numfiles/100)
    indtobeat = 0
    cpct = - 1
    for f in range(numfiles):
        cfile = allfiles[f]
        if cfile[-3:] == 'jpg' or cfile[-3:] == 'png' or cfile[-4:] == 'jpeg':
            fullimage = imread(fullpath+cfile)
            newdata = resize(fullimage,(pixwid,pixheight))
            cmean,cstdev,cblock = getimgcolors(newdata,classinterval,bounds,numclasses)
            imagedata.append(newdata)
            imagemeans.append(cmean)
            imagestdevs.append(cstdev)
            imageblocks.append(cblock)
            imageids.append(cfile)
            
        if f >= indtobeat:
            cpct += 1
            indtobeat += numonepct
            print(f"Caching images... {cpct}%",end="\r")
    
    logging.info("Image caching 100% complete")        
    
    #only including images with low enough color standard deviations (bottom 10 percent)
    stdev_threshold = np.percentile(np.asarray(imagestdevs),30)
    for data,cmean,cstdev,cblock,cfile in zip(imagedata,imagemeans,imagestdevs,imageblocks,imageids):
        if cstdev <= stdev_threshold:
            allimages["data"].append(data)
            allimages["means"].append(cmean)
            allimages["stdevs"].append(cstdev)
            allimages["block"].append(cblock)
            allimages["id"].append(cfile)
            allimages["ismatched"].append(False)
            
    #recording whether each color block has images in it
    allimages["colorblockoccupied"] = []
    for i in range(numclasses**3):
        allimages["colorblockoccupied"].append(i in allimages["block"])
    
    return allimages
    
    
    
    
# creates image cache of single color jpegs to use as test for pixelator matching system
def makesinglecolorcache(dirtomake,colors,hght,wid):
    a = -1
    totalnum = len(colors)**3
    for r in colors:
        for g in colors:
            for b in colors:
                a += 1
                curcolors = np.array([r,g,b])
                logging.debug('Making '+str(curcolors) + '(' + str(a) + '/' + str(totalnum) + ')')
                curpixels = np.ones((hght,wid,3))
                for i in range(curpixels.shape[0]):
                    for j in range(curpixels.shape[1]):
                        curpixels[i,j,:] = curcolors
                imwrite(dirtomake+'color'+str(a)+'.jpeg',curpixels)

                
                

#build image mosaic
def buildmosaic(rawimage,allimages,indwidth,indheight,usemultipletimes,classinterval,bounds,numclasses):
    mosaic = np.zeros((indheight * rawimage.shape[0], indwidth * rawimage.shape[1],3))
    numtiles = rawimage.shape[0]*rawimage.shape[1]
    
    
    numonepct = np.round(numtiles/100)
    indtobeat = 0
    cpct = - 1
    
    all_h = []
    all_l = []
    
    #create a list of remaining indices (tuples)
    remainingindices = []
    for h in range(rawimage.shape[0]):
        for l in range(rawimage.shape[1]):
            remainingindices.append((h,l))
                
    for i in range(numtiles):
        #get random indices from remaining list, match an image, mark as done
        curpixel = remainingindices[np.random.choice(range(len(remainingindices)))]
        h = curpixel[0]
        l = curpixel[1]
        all_h.append(h)  # image dimension info
        all_l.append(l)
        remainingindices.remove(curpixel)
            
        
    #actually building mosaic
    i = 0
    for (h,l) in zip(all_h,all_l):
        sh = h*indheight
        sl = l*indwidth
        colorblock = classifycolorblock(rawimage[h,l,:],classinterval,bounds,numclasses)
        mosaic[sh:sh + indheight, sl:sl + indwidth] = matchimage(rawimage[h,l,:], allimages, colorblock, usemultipletimes)
        i += 1
        if i >= indtobeat:
            cpct += 1
            indtobeat += numonepct
            print(f"Building mosaic... {cpct}%",end="\r")
        
    logging.info("Building mosaic... 100% complete")
    return mosaic
    
    
    

# match subsampled image RGB values to directory, generate large image
def matchimage(color,allimages,colorblock,usemultipletimes):
    colordiffs = []
    for i,cmean in enumerate(allimages["means"]):
        if ((not usemultipletimes and allimages["ismatched"][i]) or usemultipletimes) and (not allimages["colorblockoccupied"][colorblock] or allimages["block"][i] == colorblock):
            colordiffs.append(getcolordifference(cmean,color))
        else:
            colordiffs.append(np.nan)
    
    colordiffs = np.asarray(colordiffs)
    if np.nansum(colordiffs) == np.nan:
        outimage = np.zeros((allimages["data"][0].shape[0],allimages["data"][0].shape[1],3)) #return black square
    else:
        outind = np.nanargmin(colordiffs)
        outimage = allimages["data"][outind]
        allimages["ismatched"][outind] = True
    return outimage

    

def getcolordifference(c1,c2):
    return np.sqrt(np.sum((c1 - c2)**2))


    
    
#######################################################################################################################
#                                            PIXELATOR DRIVER FUNCTION                                                  #
#######################################################################################################################

# Eriver for pixelator- takes image to pixelate, input directory for other images, generate output image TODO: add error catching
# Input variable description:
#    o ndarray(3d) sourceimage: image RGB data read in with cv2.imread()
#    o str imagedir: directory of images to use for individual tiles in mosaic
#    o int (width/height)_images: size of final mosaic in tiles (individual, smaller images)
#    o int targetpix(widht/height): Target size of final mosaic in pixels (will be adjusted slightly)
#    o str method: way which individual images are assigned as tiles in mosaic (see buildmosaic() for options)
#    o bool usemultipletimes: If true- the same image can be used for multiple tiles
# Function variable description:
#    o int ind(width/height): Dimensions of individual tiles to be used (pixels)
#    o int final(width/height): Actual dimmensions of final mosaic (pixels)
#    o dict allimages: Python dictionary containing RGB data and descriptors for all of the "tile" options
# OUTPUT: ndarray(3d) mosaic: RGB image data for output image
def pixelator_driver(sourceimage,imagedir,width_images,height_images,targetpixwidth,targetpixheight,usemultipletimes):
    #print input settings
    logging.info('Received Image Pixelation Request:')
    logging.debug('Source image=',str(sourceimage.shape[1]) + 'x' + str(sourceimage.shape[0]))
    logging.debug('Source directory: ' + imagedir)
    logging.debug('Target final image size (individual images): '+ str(width_images) + 'x' + str(height_images))
    logging.debug('Target final image size (pixels): '+ str(targetpixwidth) + 'x' + str(targetpixheight))
    logging.debug('Settings: method='+method + ', usemultipletimes=',usemultipletimes)

    #resize input image to big pixels
    newsize = (width_images,height_images)
    pixels = resize(sourceimage, newsize)
    logging.debug('Resized image input to ' + str(pixels.shape[1]) + 'x' + str(pixels.shape[0]))

    #solve for individual pixel width and height
    logging.debug('Solving new width and height...')
    indwidth = np.round(targetpixwidth/width_images)
    if indwidth < 1 or np.isnan(indwidth):
        indwidth = 1
    else:
        indwidth = int(indwidth)
    indheight = np.round(targetpixheight/height_images)
    if indheight < 1 or np.isnan(indheight):
        indheight = 1
    else:
        indheight = int(indheight)
    finalwidth = indwidth*width_images
    finalheight = indheight*height_images
    logging.debug('Final mosaic size (pixels): '+ str(finalwidth) + 'x' + str(finalheight))
    logging.debug('Individual tile size: ' + str(indwidth) + 'x' + str(indheight))

    #cache images in directory
    logging.debug('Caching images')
    classinterval = 0.2
    bounds = np.arange(0,1.01,classinterval)*255
    numclasses = len(bounds)-1
    allimages = cacheimages(imagedir,indwidth,indheight,classinterval,bounds,numclasses)
    logging.debug('Successfully cached all images')

    #build mosaic from cached images
    logging.debug('Building image mosaic...')
    mosaic = buildmosaic(pixels,allimages,indwidth,indheight,usemultipletimes,classinterval,bounds,numclasses)
    logging.debug('Successfully built image mosaic- program completed!')

    return mosaic





#######################################################################################################################
#                                        EXAMPLE CODE TO USE PIXELATOR                                                  #
#######################################################################################################################

def example_driver():

    #file pathways
    sourcedir = 'Datasets/landscapes/'
    sourcefile = 'Datasets/landscape.jpeg'
    outfile = 'Datasets/test_landscape.jpeg'

    #input dimensions/resolution for mosaic
    width_images = 160 #how many tiles wide/tall the mosaic should be
    height_images = 120
    targetpixwidth = 2000
    targetpixheight = 1500

    #settings for mosaic generation
    usemultipletimes = True #if this is true, the same photo can be used multiple times (otherwise it can't)
    
    #reading image
    sourceimage = imread(sourcefile)

    #running pixelator
    mosaic = pixelator_driver(sourceimage, sourcedir, width_images, height_images, targetpixwidth, targetpixheight,
                              usemultipletimes)

    #saving image
    imwrite(outfile, mosaic)



    
    
if __name__ == "__main__":
    
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    #run example driver
    example_driver()
    
    
    
    
    
    