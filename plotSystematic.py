#!/usr/bin/env python
import Utilities.plot_functions as plotter
import Utilities.helper_functions as helper
import argparse
import ROOT
import Utilities.config_object as config_object
import Utilities.UserInput as UserInput
import os
from Utilities.ConfigHistFactory import ConfigHistFactory 
from Utilities.prettytable import PrettyTable
import math
import sys
import array
import datetime
from Utilities.scripts import makeSimpleHtml
from IPython import embed
import logging

def getComLineArgs():
    parser = UserInput.getDefaultParser()
    parser.add_argument("-s", "--selection", type=str, required=True,
                        help="Specificy selection level to run over")
    parser.add_argument("-b", "--branches", type=str, default="all",
                        help="List (separate by commas) of names of branches "
                        "in root and config file to plot") 
    parser.add_argument("--systematics", type=str, required=True,
                        help="Specificy systematics to plot")
    return parser.parse_args()

def main():
    args = getComLineArgs()
    ROOT.gROOT.SetBatch(True)

    branches = [x.strip() for x in args.branches.split(",")]
    
    (plot_path, html_path) = helper.getPlotPaths(args.selection, args.folder_name, True)

    meta_info = '-'*80 + '\n' + \
        'Script called at %s\n' % datetime.datetime.now() + \
        'The command was: %s\n' % ' '.join(sys.argv) + \
        '-'*80 + '\n'

    rtfile = ROOT.TFile(args.hist_file)

    for branch in args.branches.split(","):
        with open("temp.txt", "w") as mc_file:
            mc_file.write(meta_info)
            mc_file.write("Selection: %s" % args.selection)
            mc_file.write("\nPlotting branch: %s\n" % branch)

        systematics = args.systematics.split(",")
        systs = "_".join(systematics)
        plot_name = "_".join([branch, systs]) if args.append_to_name == "" \
                else "_".join([branch, systs, args.append_to_name])
        hist_stack = ROOT.THStack("stack_"+branch, "stack_"+branch)
        file_names = args.files_to_plot.split(",")
        for i, file_name in enumerate(file_names):
            systematic = systematics[i]
            central_hist = 0
            for chan in args.channels.split(","):
                hist_name = file_name.replace("_standalone", "") + "/"+ "_".join([branch, chan])
                uphist_name = hist_name.replace(chan, "_".join([systematic+"Up", chan]))
                downhist_name = hist_name.replace(chan, "_".join([systematic+"Down", chan]))

                if not central_hist:
                    central_hist = rtfile.Get(hist_name)
                    up_hist = rtfile.Get(uphist_name)
                    down_hist = rtfile.Get(downhist_name)
                    central_hist.Draw()
                else:
                    if i == 0 or file_name != file_names[i-1]:
                        central_hist.Add(rtfile.Get(hist_name))
                    up_hist.Add(rtfile.Get(uphist_name))
                    down_hist.Add(rtfile.Get(downhist_name))
            path = "/cms/kdlong" if "hep.wisc.edu" in os.environ['HOSTNAME'] else \
                "/afs/cern.ch/user/k/kelong/work"
            config_factory = ConfigHistFactory(
                "%s/AnalysisDatasetManager" % path,
                args.selection.split("_")[0],
            )
            scale_fac = 1
            scale = False
            # Normalize to data in CR
            if file_name == "wz-mgmlm":
                scale_fac = (191-(28.78+3.84+18.35+22.27))/144.82
            elif file_name in ["wz", "wz_standalone"]:
                scale_fac = (191-(28.78+3.84+18.35+22.27))/183.25
            elif file_name in ["wz-powheg", "wz-powheg_standalone"]:
                scale_fac =(191-(28.78+3.84+18.35+22.27))/139.43
            if scale:
                central_hist.Scale(scale_fac)
                up_hist.Scale(scale_fac)
                down_hist.Scale(scale_fac)
            with open("temp.txt", "a") as mc_file:
                mc_file.write("\nYield for %s is %0.2f" % (file_name, central_hist.Integral()))
            
            config_factory.setHistAttributes(central_hist, branch, file_name)
            config_factory.setHistAttributes(up_hist, branch, file_name)
            config_factory.setHistAttributes(down_hist, branch, file_name)
            central_hist.SetMinimum(0.001)
            central_hist.SetFillColor(0)
            up_hist.SetFillColor(0)
            down_hist.SetFillColor(0)
            
            central_hist.SetLineStyle(1)
            central_hist.SetLineWidth(2)
            up_hist.SetLineWidth(2)
            down_hist.SetLineWidth(2)
            up_hist.SetLineStyle(5)
            down_hist.SetLineStyle(5)

            hist_stack.Add(central_hist)
            hist_stack.Add(up_hist)
            hist_stack.Add(down_hist)

        canvas_dimensions = [800, 800] if "unrolled" not in branch else [1200, 800]
        canvas = ROOT.TCanvas("canvas", "canvas", *canvas_dimensions)
        hist_stack.Draw("nostack hist")
        hist_stack.SetMinimum(central_hist.GetMinimum()*args.scaleymin)
        hist_stack.SetMaximum(central_hist.GetMaximum()*args.scaleymax)

        text_box = ROOT.TPaveText(0.65, 0.85-0.1*len(systematics), 0.9, 0.85, "NDCnb")
        text_box.SetFillColor(0)
        text_box.SetTextFont(42)
        text_box.AddText("Sytematic variation")
        for s in systematics:
            text_box.AddText(s)
        for line, h in zip(text_box.GetListOfLines()[1:], hist_stack.GetHists()[::3]):
            line.SetTextColor(h.GetLineColor())
        text_box.Draw()
        if args.logy:
            canvas.SetLogy()

        if not args.no_ratio:
            canvas = plotter.splitCanvas(canvas, canvas_dimensions,
                    "syst./cent.",
                    [float(i) for i in args.ratio_range]
            )
        helper.savePlot(canvas, plot_path, html_path, plot_name, True, args)
        makeSimpleHtml.writeHTML(html_path.replace("/plots",""), args.selection)

if __name__ == "__main__":
    main()
