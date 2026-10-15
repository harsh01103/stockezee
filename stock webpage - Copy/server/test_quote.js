import yahooFinance from "yahoo-finance2";

yahooFinance.quote("RELIANCE.NS").then(quote => {
    console.log("bid:", quote.bid);
    console.log("ask:", quote.ask);
    console.log("bidSize:", quote.bidSize);
    console.log("askSize:", quote.askSize);
    console.log("regularMarketVolume:", quote.regularMarketVolume);
});
