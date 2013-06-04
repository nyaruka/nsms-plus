
var colors = Highcharts.getOptions().colors;
var highcharts = {};

/**
 * Build a highcharts series from our metric data
 */
function create_highchart_series(chart, metric, click_series_fn) {

    if (metric.color == null) {
        var new_color = colors[0];
        for (var j=0; j<colors.length; j++) {
            var used = false;
            for (var k=0; k<chart.metrics.length; k++) {
                if (chart.metrics[k].color == colors[j]) {
                    used=true;
                    break;
                }
            }
            if (!used) {
                new_color = colors[j];
                break;
            }
        }
        metric.color = new_color;
    }

    var label = metric.label;
    if (label == null) {
        label = metric.name + " (" + metric.agg + ")";
    }

    var r = hexToR(metric.color);
    var g = hexToG(metric.color);
    var b = hexToB(metric.color);
    if (metric.series != null) {
        return {
            name : label,
            type : metric.type,
            color : "rgba(" + r + "," + g + "," + b + ", .8)",
            yAxis : metric.left ? 0 : 1,
            data: metric.series.data,
            labels: metric.series.labels,
            stack : metric.left ? 0 : 1,
            events: {
                click: function(event) {
                    click_series_fn(chart, this.index, event.point.x);
                }
            }
        };
    }
    return null;
}

function click_chart(evt) {

    var target = evt.currentTarget;
    if (evt.currentTarget.container) {
        target = evt.currentTarget.container;
    }

    // see if we are on the right target, otherwise walk up until we find it
    var classes = target.classList;
    if (!classes || classes.length != 1 || classes[0] != "highcharts-container") {
        target = $(target).parents('.highcharts-container')[0];
    }

    var hc = highcharts[target.id];
    if (hc.click_chart) {
        hc.click_chart(hc.chart)
    }
}
/**
 * Creates a data URI to download in-page chart JSON data as a CSV
 */
function chart_to_csv(chart) {

    var lines = 'period';
    var labels = [];

    for (var i in chart.metrics) {
        lines +=  ',' + chart.metrics[i].name;

        if (chart.metrics[i].series) {
            labels = chart.metrics[i].series.labels;
        }
    }
    lines += '\r\n';

    for (var i in labels) {

        lines += labels[i];
        for (var j in chart.metrics) {
            if (chart.metrics[j].series) {
            lines += "," + chart.metrics[j].series.data[i];
            } else {
                lines += ",-";
            }
        }
        lines += '\r\n';
    }

    if (navigator.appName != 'Microsoft Internet Explorer') {
        window.open('data:text/csv;charset=utf-8;filename=chart-export.csv,' + escape(lines), 'chart-export.csv');
    } else {
        var popup = window.open('','csv','');
        popup.document.body.innerHTML = '<pre>' + lines + '</pre>';
    }
}


/**
 * Render the chart spec into the given container
 */
function render_chart(chart, container, options) {

    // consider any options provided
    var click_chart_fn = null;
    var click_series_fn = null;
    var show_legend = false;
    var manual_fetching = false;
    if (options) {

        if (options.show_legend) {
            show_legend = options.show_legend;
        }

        if (options.manual_fetching) {
            manual_fetching = options.manual_fetching
        }
        click_chart_fn = options.click_chart;
        click_series_fn = options.click_series;

    }

    var series = [];
    var labels = [];
    if (options.check_fetched) {
        manual_fetching = true;
        for (var i in chart.metrics) {
            var metric = chart.metrics[i];
            var hc_series = create_highchart_series(chart, metric, click_series_fn);
            if (hc_series != null) {
                series.push(hc_series);
                if (metric.series.labels) {
                    labels = metric.series.labels
                }
            }
        }
    }

    var linewidth;
    if(chart.labels.show_axis_y == true) {
        linewidth = 1;
    }else{
        linewidth = 0;        
    }

    var hc = new Highcharts.Chart({
        credits: { enabled: false },
        chart: {
            events: { click : click_chart },
            renderTo: container,
            defaultSeriesType: "line"
        },
        title: {
            text: chart.labels.title
        },
        subtitle: {
            text: chart.labels.subtitle
        },
        legend: {
            borderWidth: 1,
            enabled: show_legend
        },
        xAxis: {
            categories: labels,
            title: {
                text: chart.labels.x
            }
        },
        yAxis: [
            {
                title: { text: chart.labels.y },
                min: 0,
                lineWidth:linewidth,
                minorTickInterval: 'auto',
                minorTickPosition: 'outside',
                minorGridLineColor: '#FFFFFF',
                minorTickWidth:linewidth,
                minorTickLength: 4
            },{
                title: { text: chart.labels.y2 },
                min: 0,
                opposite:true
            }
        ],
        plotOptions: {
            series: {
                stacking: chart.options.stacked
            }
        },

        redraw: true,
        series: series
    });

    hc.chart_id = chart.id;
    $(".highcharts-title,.highcharts-subtitle,.highcharts-axis").unbind('click');
    $(".highcharts-title,.highcharts-subtitle,.highcharts-axis").on('click', function(e) {
        e.preventDefault();
        click_chart(e);
    });

    chart.highchart = hc;
    highcharts[hc.container.id] = { chart:chart, click_chart:click_chart_fn };

    // trigger a fetch for all of our data if requested
    if (!manual_fetching) {
        for (var j=0; j<chart.metrics.length; j++) {
            fetch_data(chart, chart.metrics[j], function(e) {
                e.chart.highchart.addSeries(create_highchart_series(e.chart, e.metric, click_chart_fn));
                e.chart.highchart.xAxis[0].setCategories(e.metric.series.labels);
            });
        }
    }

    return hc;

}

/**
 * Fetch the data for a given series
 */
function fetch_data(chart, metric, callback, extra_data) {

    // console.log("Fetching data for " + metric.name + " (" + metric.agg + ")");
    if (!metric.series) {
        var link = "/charts/chart/series?_format=json&dataset=" + chart.dataset + "&metric=" + metric.name + "&interval=" + chart.interval + "&aggregate=" + metric.agg;

        // console.log(link);
        var filters = "";
        for (var i in metric.filters) {
            var filter = metric.filters[i];
            filters += filter.field + ":" + filter.value;
            if (i<metric.filters.length - 1) {
                filters += ",";
            }
        }

        if (filters.length > 0) {
            link += "&filters=" + filters;
        }

        $.getJSON(link,
            function(data){
                metric.series = data.series;
                callback({ chart: chart, metric: metric, data: extra_data});
            }
        );
    } else {
        callback({ chart: chart, metric: metric, data: extra_data});
    }
}

var zoomed_chart;
function zoom_chart(chart) {
    zoomed_chart = chart;
    $("#zoom_modal").attr("chart_id", chart.id);
    $("#zoom_modal").modal('show');
    render_chart(chart, "zoomed_chart", { show_legend:true, check_fetched: true, click_series: click_series } );
}

function click_series(chart, metric_index, x) {

    var metric = chart.metrics[metric_index];
    var filters = '';
    if (metric.filters.length > 0) {
        filters = '&filters=';
        var delim = '';
        for (var i in metric.filters) {
            filters += delim + metric.filters[i].field + ":" + metric.filters[i].value;
            delim = ',';
        }
    }
    window.open('/charts/chart/detail?dataset=' + chart.dataset + '&interval=' + chart.interval + '&metric=' + metric.name + '&bucket=' + x + filters);
}

function edit_chart() {
    var chart_id = $("#zoom_modal").attr("chart_id");
    document.location.href = "/charts/chart/editor?chart=" + chart_id;
}

function close() {
    $("#zoom_modal").modal('hide');
}

function export_chart() {
    chart_to_csv(zoomed_chart);
}

