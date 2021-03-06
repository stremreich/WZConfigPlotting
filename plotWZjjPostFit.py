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
from collections import OrderedDict
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
    parser.add_argument("--backgroundOnly", action='store_true',
                        help="Use background only fit rather than s+b")
    parser.add_argument("--noCR", action='store_true',
                        help="Remove control region from fit distribution")
    parser.add_argument("-b", "--branches", type=str, default="all",
                        help="List (separate by commas) of names of branches "
                        "in root and config file to plot") 
    return parser.parse_args()

def getFormattedYieldAndError(integral, error, sigfigs):
    result = "%0.1f" % round(integral, 1)

    error_digits = 0
    error_string = " $\pm$ %i"
    if len(result.split(".")) == 2:
        error_digits = len(result.split(".")[1])
        error_string = " $\pm$ %.{digits}f".format(digits=error_digits)
    error = round(error, error_digits)

    return result + (error_string % error)

def makeLogFile(channels, hist_info, args):
    with open("temp.txt", "w") as log_file:
        meta_info = '-'*80 + '\n' + \
            'Script called at %s\n' % datetime.datetime.now() + \
            'The command was: %s\n' % ' '.join(sys.argv) + \
            '-'*80 + '\n'
        log_file.write(meta_info)
        log_file.write("Selection: %s" % args.selection)
        log_file.write("\nLuminosity: %0.2f fb^{-1}\n" % (args.luminosity))
        log_file.write('-'*80 + '\n')
    columns = ["Process"] + ["\\"+c for c in channels] + ["Total Yield"]
    yield_table = PrettyTable(columns)
    yield_info = OrderedDict()

    formatted_names = { "wz-powheg" : "WZ (POWHEG)",
        "wz-mgmlm" : "WZ (MG MLM)",
        "QCD-WZjj" : "QCD-WZjj",
        "EW-WZjj" : "EW-WZjj",
        "wzjj-ewk" : "WZjj EWK",
        "wzjj-ewk_filled" : "WZjj EWK",
        "wzjj-vbfnlo" : "WZjj EWK (VBFNLO)",
        "nonprompt" : "Nonprompt",
        "top-ewk" : "t+V/VVV",
        "zg" : "Z$\gamma$",
        "vv-powheg" : "VV (POWHEG)",
        "vv" : "VV",
        "wz" : "WZ (MG5\_aMC)",
        "wz-powheg" : "WZ (POWHEG)",
        "predyield" : "Pred. Background",
        "data_2016" : "Data",
        "data" : "Data",
        "data_2016H" : "Data (2016H)",
    }

    sigfigs = 3
    for name, entry in hist_info.iteritems():
        if "aqgc" in name:
            continue
        for i, chan in enumerate(channels):
            # Channels should be ordered the same way as passed to the histogram
            # This bin 0 is the underflow, bin 1 is total, and bin 2
            # is the first bin with channel content (mmm/emm/eem/eee by default)
            if name == "data":
                yield_info[chan] = "%i" % entry[chan][0] 
            else:
                yield_info[chan] = getFormattedYieldAndError(entry[chan][0], entry[chan][1], sigfigs)
        if name == "data":
            yield_info["Total Yield"] = "%i" % entry["total"][0] 
        else:
            yield_info["Total Yield"] = getFormattedYieldAndError(entry["total"][0], entry["total"][1], sigfigs)
        yield_table.add_row([formatted_names[name]] + yield_info.values())
    with open("temp.txt", "a") as log_file:
        log_file.write(yield_table.get_latex_string())


def histFromGraph(graph, name):
    nentries = graph.GetN()
    hist = ROOT.TH1D(name, name, nentries, 0, nentries)
    for i in range(nentries):
        x = array.array('d', [0])
        y = array.array('d', [0])
        graph.GetPoint(i, x, y)
        hist.Fill(x[0], y[0])
    return hist

def removeControlRegion(hist):
    nbins = hist.GetNbinsX()-1
    name = hist.GetName() +"_noCR"
    new_hist = ROOT.TH1D(name, name, nbins, 0, nbins)
    for i in range(2, hist.GetNbinsX()+1):
        new_hist.SetBinContent(i-1, hist.GetBinContent(i))
        new_hist.SetBinError(i-1, hist.GetBinError(i))
    return new_hist

def rebinMTWZ(hist, hist_name):
    binning = array.array('d', [0,100,200,300,400,500,700,1000,1500,2000]) 
    new_hist = ROOT.TH1D(hist_name, hist_name, len(binning)-1, binning)
    for i in range(hist.GetNbinsX()+1):
        new_hist.SetBinContent(i, hist.GetBinContent(i))
        new_hist.SetBinError(i, hist.GetBinError(i))
    return new_hist

def main():
    args = getComLineArgs()
    ROOT.gROOT.SetBatch(True)

    (plot_path, html_path) = helper.getPlotPaths(args.selection, args.folder_name, True)

    meta_info = '-'*80 + '\n' + \
        'Script called at %s\n' % datetime.datetime.now() + \
        'The command was: %s\n' % ' '.join(sys.argv) + \
        '-'*80 + '\n'

    rtfile = ROOT.TFile(args.hist_file)

    channels = args.channels.split(",")
    hist_info = {}
    hist_info["predyield"] = OrderedDict({"mmm" : [0,0],
        "emm" : [0,0],
        "eem" : [0,0],
        "eee" : [0,0],
        "total" : [0,0],
        }
    )
    for branch in args.branches.split(","):
        with open("temp.txt", "w") as mc_file:
            mc_file.write(meta_info)
            mc_file.write("Selection: %s" % args.selection)
            mc_file.write("\nPlotting branch: %s\n" % branch)

        plot_name = branch 
        if args.append_to_name:
            plot_name += "_" + args.append_to_name
        hist_stack = ROOT.THStack("stack_postfit", "stack_postfit")
        signal_stack = ROOT.THStack("signalstack_prefit", "sig_prefit")
        data_hist = 0
        plot_groups = args.files_to_plot.split(",")
        if not args.no_data:
            plot_groups.append("data")
        for i, plot_group in enumerate(plot_groups):
            hist_info[plot_group] = OrderedDict({"mmm" : [0,0],
                "emm" : [0,0],
                "eem" : [0,0],
                "eee" : [0,0],
                "total" : [0,0],
                }
            )
            isSignal = False
            central_hist = 0
            for chan in channels:
                folder = "shapes_fit_b" if args.backgroundOnly else "shapes_fit_s"
                if "aqgc" in plot_group:
                    isSignal = True
                    folder = "shapes_prefit"
                hist_name = "/".join([folder, chan, plot_group if plot_group != "wzjj-ewk_filled" else "EW-WZjj"])

                hist = rtfile.Get(hist_name)
                if hist.InheritsFrom("TGraph"):
                    hist = histFromGraph(hist, "_".join([plot_group, chan]))
                if args.noCR:
                    hist = removeControlRegion(hist)
                if "MTWZ" in plot_name:
                    hist = rebinMTWZ(hist, hist_name)
                if not central_hist:
                    central_hist = hist
                    central_hist.SetName(plot_group)
                else:
                    central_hist.Add(hist)
                error = array.array('d', [0])
                integral = hist.IntegralAndError(0, hist.GetNbinsX(), error)
                hist_info[plot_group][chan] = (integral, error[0])
                with open("temp.txt", "a") as mc_file:
                    mc_file.write("\nYield for %s in channel %s is %0.3f $pm$ %0.3f" % 
                            (plot_group, chan, integral, error[0]))
            path = "/cms/USER" if "hep.wisc.edu" in os.environ['HOSTNAME'] else \
                "/afs/cern.ch/user/k/USER/work"
            path = path.replace("USER", os.environ["USER"])
            config_factory = ConfigHistFactory(
                "%s/AnalysisDatasetManager" % path,
                args.selection.split("_")[0],
            )
            scale_fac = 1
            scale = False
            error = array.array('d', [0])

            integral = central_hist.IntegralAndError(0, central_hist.GetNbinsX(), error)
            hist_info[plot_group]["total"] = (integral, error[0])
            with open("temp.txt", "a") as mc_file:
                mc_file.write("\nCombined yield for %s is %0.3f $pm$ %0.3f" % (plot_group, integral, error[0]))
            
            config_factory.setHistAttributes(central_hist, branch, plot_group)
            
            if plot_group != "data" and not isSignal:
                hist_stack.Add(central_hist)
            elif isSignal:
                signal_stack.Add(central_hist)
            else:
                data_hist = central_hist
                data_hist.Sumw2(False)
                data_hist.SetBinErrorOption(ROOT.TH1.kPoisson)
        if not signal_stack.GetHists():
            signal_stack = 0
        error_hist = 0 
        bkerror_hist = 0
        folder = "shapes_fit_b" if args.backgroundOnly else "shapes_fit_s"
        for chan in channels:
            bkerror_chan = rtfile.Get("/".join([folder, chan, "total_background"]))
            error_chan = rtfile.Get("/".join([folder, chan, "total"]))
            if args.noCR:
                error_chan = removeControlRegion(error_chan)
                bkerror_chan = removeControlRegion(bkerror_chan)
            if "MTWZ" in plot_name:
                error_chan = rebinMTWZ(error_chan, "tmp")
                bkerror_chan = rebinMTWZ(bkerror_chan, "bktmp")
            if not error_hist:
                error_hist = error_chan.Clone("errors")
                bkerror_hist = bkerror_chan.Clone("bkerrors")
            else:
                error_hist.Add(error_chan)
                bkerror_hist.Add(bkerror_chan)
            error = array.array('d', [0])
            integral = error_chan.IntegralAndError(0, error_chan.GetNbinsX(), error)
            hist_info["predyield"][chan] = (integral, error[0])

        error = array.array('d', [0])
        integral = bkerror_hist.IntegralAndError(1, bkerror_hist.GetNbinsX(), error)
        hist_info["predyield"]["total"] = (integral, error[0])

        canvas = helper.makePlots([hist_stack], [data_hist], plot_name, args, signal_stacks=[signal_stack],
                        errors=[error_hist] if error_hist else [])
        if "CR" not in plot_name and "unrolled" in plot_name:
            ratioPad = canvas.GetListOfPrimitives().FindObject("ratioPad")
            stackPad = canvas.GetListOfPrimitives().FindObject("stackPad")
            ratiohist = ratioPad.GetListOfPrimitives().FindObject('%s_canvas_central_ratioHist' % plot_name)
            xaxis = hist.GetXaxis()
            maximum = hist_stack.GetHistogram().GetMaximum()
            for i in [4,8]:
                line = ROOT.TLine(xaxis.GetBinUpEdge(i), hist_stack.GetMinimum(), xaxis.GetBinUpEdge(i), maximum)
                line.SetLineStyle(7)
                line.SetLineColor(ROOT.kGray+2)
                line.SetLineWidth(2)
                stackPad.cd()
                line.Draw()
                ROOT.SetOwnership(line, False)
            for i, label in enumerate(["#in [2.5, 4]", "#in [4, 5]", "#geq 5   "]):
                xmin = 0.22 + 0.24*i +0.05*(i==2)
                ymin = 0.15 if i == 2 else 0.5
                ymax = ymin + (0.2 if i ==0 else 0.18)
                xmax = xmin + (0.19 if i ==0 else 0.175)
                text_box = ROOT.TPaveText(xmin, ymin, xmax, ymax, "NDCnb")
                text_box.SetFillColor(0)
                text_box.SetTextFont(42)
                text_box.AddText("#Delta#eta_{jj} %s" % label)
                text_box.Draw()
                ROOT.SetOwnership(text_box, False)

        makeLogFile(channels, hist_info, args)
        helper.savePlot(canvas, plot_path, html_path, plot_name, True, args)
        makeSimpleHtml.writeHTML(html_path.replace("/plots",""), args.selection)

if __name__ == "__main__":
    main()


