#!/usr/bin/env python3

from argparse import ArgumentParser


parser = ArgumentParser('Apply a model to a (test) source sample and create friend trees to inject it inthe original ntuple')
parser.add_argument('inputModel')
parser.add_argument('trainingDataCollection')
parser.add_argument('inputSourceFileList')
parser.add_argument('outputDir')
parser.add_argument("-b", help="batch size ",default="-1")
parser.add_argument("--gpu",  help="select specific GPU", metavar="OPT", default="")
parser.add_argument("--unbuffered",   help="do not read input in memory buffered mode (for lower memory consumption on fast disks)", default=False, action="store_true")


args = parser.parse_args()
batchsize = int(args.b)


import imp
from DeepJetCore.DataCollection import DataCollection
from DeepJetCore.compiled.c_trainDataGenerator import trainDataGenerator
import tempfile
import atexit
import os
from keras.models import load_model
from keras import backend as K
from DeepJetCore.customObjects import get_custom_objects
from DeepJetCore.training.gpuTools import DJCSetGPUs

DJCSetGPUs(args.gpu)

custom_objs = get_custom_objects()

model=load_model(args.inputModel, custom_objects=custom_objs)
dc = DataCollection(args.trainingDataCollection)

outputs = []
inputdir = os.path.abspath(os.path.dirname(args.inputSourceFileList))
os.system('mkdir -p '+args.outputDir)

with open(args.inputSourceFileList, "r") as f:
    for inputfile in f:
        inputfile = inputfile.replace('\n', '')
        use_inputdir = inputdir
        if inputfile[0] == "/":
            use_inputdir=""
        outfilename = "pred_"+os.path.basename( inputfile )
        
        td = dc.dataclass()

        if inputfile[-5:] == 'djctd':
            if args.unbuffered:
                td.readFromFile(use_inputdir+"/"+inputfile)
            else:
                td.readFromFileBuffered(use_inputdir+"/"+inputfile)
        else:
            print('converting '+inputfile)
            td.readFromSourceFile(use_inputdir+"/"+inputfile, dc.weighterobjects, istraining=False)
        

        print('predicting ',inputfile)
        gen = trainDataGenerator()
        if batchsize < 1:
            batchsize = dc.getBatchSize()
        print('batch size',batchsize)
        gen.setBatchSize(batchsize)
        gen.setSquaredElementsLimit(dc.batch_uses_sum_of_squares)
        gen.setSkipTooLargeBatches(False)
        gen.setBuffer(td)
        
        def genfunc():
            while(not gen.isEmpty()):
                d = gen.getBatch()
                yield d.transferFeatureListToNumpy() , d.transferTruthListToNumpy()
                
        predicted = model.predict_generator(genfunc(),
                                            steps=gen.getNBatches(),
                                            max_queue_size=1,
                                            use_multiprocessing=False,verbose=1)
        
        
        x = td.transferFeatureListToNumpy()
        w = td.transferWeightListToNumpy()
        y = td.transferTruthListToNumpy()
        
        td.clear()
        gen.clear()
        
        if not type(predicted) == list: #circumvent that keras return only an array if there is just one list item
            predicted = [predicted]   
        td.writeOutPrediction(predicted, x, y, w, args.outputDir + "/" + outfilename, use_inputdir+"/"+inputfile)
        
        outputs.append(outfilename)
        
    
    
with open(args.outputDir + "/outfiles.txt","w") as f:
    for l in outputs:
        f.write(l+'\n')
    
    
    
    
    
